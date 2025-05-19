#!/usr/bin/python3

"""Copyright (c) 2019, Douglas Otwell

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import dbus
import re
import subprocess
import json
import threading
from advertisement import Advertisement
from service import Application, Service, Characteristic, Descriptor


GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"

class WifiAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        self.add_local_name("Wifi Setup")
        self.include_tx_power = True

class WifiScanningService(Service):
    WIFI_SVC_UUID = "00000001-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, index):
        Service.__init__(self, index, self.WIFI_SVC_UUID, True)
        self.status_char = WifiStatusCharacteristic(self)
        self.scan_char = ScanWifiCharacteristic(self, self.status_char)

        self.add_characteristic(self.status_char)
        self.add_characteristic(self.scan_char)

class ScanWifiCharacteristic(Characteristic):
    WIFI_CHARACTERISTIC_UUID = "00000003-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service, status_char):
        Characteristic.__init__(
                self, self.WIFI_CHARACTERISTIC_UUID,
                ["read", "write"], service)
        self.status_char = status_char
        self.add_descriptor(ScanWifiDescriptor(self))

    def configure_wifi_nmcli(self, ssid: str, password: str):
        return subprocess.run([
            "sudo", "nmcli", "connection", "add",
            "type", "wifi",
            "con-name", ssid,
            "ssid", ssid,
            "ifname", "wlan0",
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", password,
            "connection.autoconnect", "yes",
            "--", "save", "yes"
        ], capture_output=True, text=True, check=True)

    def connect_wifi_nmcli(self, ssid:str):
        return subprocess.run([
            "sudo", "nmcli", "connection", "up", ssid
        ], check=True)
        
    def get_nearby_wifi(self):
        output = subprocess.check_output(
        ["sudo", "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list"]
        ).decode("utf-8")

        # Get list of saved (known) connections
        saved_output = subprocess.check_output(
            ["nmcli", "-t", "-f", "NAME", "connection", "show"]
        ).decode("utf-8")

        saved_ssids = set([line.strip() for line in saved_output.strip().split('\n') if line.strip()])

        networks = []
        pattern = re.compile(r'^(.*?):(\d+):([^:]*):?(.*)?$')

        for line in output.strip().split('\n'):
            match = pattern.match(line.strip())
            if match:
                ssid = match.group(1).strip()
                signal = int(match.group(2).strip())
                security = match.group(3).strip() or "OPEN"
                in_use_field = match.group(4).strip()
                in_use = True if in_use_field == '*' else False

                if ssid:  # skip hidden/empty SSIDs
                    networks.append({
                        "ssid": ssid,
                        "signal": signal,
                        "security": security,
                        "in_use": in_use,
                        "is_saved": ssid in saved_ssids
                    })

        networks = sorted(networks, key=lambda x: x["in_use"], reverse=True)

        json_str = json.dumps(networks)
        value = [dbus.Byte(b) for b in json_str.encode("utf-8")]

        return value

    def decode_dbus_array(self,value):
        return bytes(value).decode("utf-8")

    def ReadValue(self, options):
        value = self.get_nearby_wifi()
        return value

    def WriteValue(self, value, options):
        try:
            data = json.loads(bytes(value).decode("utf-8"))
            ssid = data.get("ssid")
            password = data.get("password")
            self.configure_wifi_nmcli(ssid,password)
            self.connect_wifi_nmcli(ssid)

            msg = {"status":"success", "message": f"Successfully connected to {ssid}"}
            self.status_char.set_status(str(msg))
        except json.JSONDecodeError as e:
            msg = {"status":"failed", "error": "Invalid JSON format:", "details": str(e)}
            self.status_char.set_status(str(msg))
        except subprocess.CalledProcessError as e:
            msg = {"status":"failed", "error": "Wi-Fi connection failed", "details": e.stderr}
            self.status_char.set_status(str(msg))
        except Exception as e:
            msg = {"status":"failed", "error": "Something went wrong.","details":str(e)}
            self.status_char.set_status(str(msg))
        
        return value

class WifiStatusCharacteristic(Characteristic):
    WIFI_STATUS_UUID = "00000004-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(
            self, self.WIFI_STATUS_UUID,
            ["read"],
            service)
        self.value = []

    def set_status(self, message):
        self.value = [dbus.Byte(b) for b in message.encode("utf-8")]
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.value}, [])

    def ReadValue(self, options):
        return self.value

class ScanWifiDescriptor(Descriptor):
    WIFI_DESCRIPTOR_UUID = "2901"
    WIFI_DESCRIPTOR_VALUE = "Scans nearby wifi networks"

    def __init__(self, characteristic):
        Descriptor.__init__(
                self, self.WIFI_DESCRIPTOR_UUID,
                ["read"],
                characteristic)

    def ReadValue(self, options):
        value = []
        desc = self.WIFI_DESCRIPTOR_VALUE

        for c in desc:
            value.append(dbus.Byte(c.encode()))

        return value

class BLEServer:
    def __init__(self):
        self.app = Application()
        self.app.add_service(WifiScanningService(0))
        self.adv = WifiAdvertisement(0)
        self.running = False
        self.thread = None

    def run_ble(self):
        self.app.register()
        self.adv.register()
        self.running = True
        try:
            self.app.run()
        except Exception as e:
            print("BLE stopped:", str(e))

    def start(self):
        if not self.running:
            self.thread = threading.Thread(target=self.run_ble)
            self.thread.daemon = True
            self.thread.start()

    def stop(self):
        if self.running:
            self.app.quit()
            self.running = False


if __name__ == "__main__":
    app = Application()
    app.add_service(WifiScanningService(0))
    app.register()

    adv = WifiAdvertisement(0)
    adv.register()

    try:
        app.run()
    except KeyboardInterrupt:
        app.quit()
