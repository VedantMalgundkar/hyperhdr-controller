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
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dbus
import re
import subprocess
import json
import threading
import time
from advertisement import Advertisement
from service import Application, Service, Characteristic, Descriptor
from utils.shared_services import configure_wifi_nmcli, connect_wifi_nmcli, scan_wifi_around, delete_wifi_connection
from exceptions import InvalidWifiRequest

GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"


class WifiAdvertisement(Advertisement):
    def __init__(self, index):
        Advertisement.__init__(self, index, "peripheral")
        self.add_local_name(self.getHostName())
        self.include_tx_power = True
        self.add_service_uuid("00000001-710e-4a5b-8d75-3e5b444bc3cf")

    def getHostName(self):
        host_info = self.get_hostname()
        if host_info["status"] == "success":
            host = host_info["hostname"]
            if "-" in host:
                host = host.split("-")[0]
            return host
        else:
            return "Wifi-Setup"

    def get_hostname(self):
        try:
            result = subprocess.run(
                ["hostname"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )

            return {"status": "success", "hostname": result.stdout.strip()}

        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "error": e.stderr.strip() if e.stderr else str(e),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


class WifiScanningService(Service):
    WIFI_SVC_UUID = "00000001-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, index):
        Service.__init__(self, index, self.WIFI_SVC_UUID, True)
        self.status_char = WifiStatusCharacteristic(self)
        self.scan_char = ScanWifiCharacteristic(self, self.status_char)
        self.wifi_connect_char = writeWifiActionCharacteristic(self,self.status_char)
        self.ip_char = GetIpAdddrCharacteristic(self)
        self.mac_char = GetMacCharacteristic(self)

        self.add_characteristic(self.status_char)
        self.add_characteristic(self.scan_char)
        self.add_characteristic(self.ip_char)
        self.add_characteristic(self.mac_char)
        self.add_characteristic(self.wifi_connect_char)

class ScanWifiCharacteristic(Characteristic):
    WIFI_CHARACTERISTIC_UUID = "00000003-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service, status_char):
        Characteristic.__init__(
            self, self.WIFI_CHARACTERISTIC_UUID, ["read", "write"], service
        )
        self.status_char = status_char

    def decode_dbus_array(self, value):
        return bytes(value).decode("utf-8")
    
    def safe_json_ble_payload(self, networks, max_bytes=450):
        packed = []
        total_bytes = 2

        for i, net in enumerate(networks):
            net_json = json.dumps(net, separators=(",", ":"))
            net_bytes = len(net_json.encode("utf-8"))

            if packed:
                net_bytes += 1
                
            if total_bytes + net_bytes > max_bytes:
                break

            packed.append(net)
            total_bytes += net_bytes

        json_str = json.dumps(packed, separators=(",", ":"))
        json_bytes = json_str.encode("utf-8")

        return [dbus.Byte(b) for b in json_bytes]

    def ReadValue(self, options):
        try:
            res = scan_wifi_around()
            networks = res.get("networks", [])
            return self.safe_json_ble_payload(networks, max_bytes=450)
        except Exception as e:
            print(f"Error in ReadValue: {e}")
            return list("error".encode())

    def WriteValue(self, value, options):
        
        try:
            # Parse the data first
            data = json.loads(bytes(value).decode("utf-8"))
            ssid = data.get("s")
            password = data.get("p")
            
            # Validate input
            if not ssid or not password:
                raise ValueError("Missing SSID or password")
            
            # Set initial status
            self.status_char.set_status(json.dumps({
                "status": "connecting", 
                "message": f"Connecting to {ssid}..."
            }))
            
            # Start WiFi connection in background thread
            def wifi_connection_task():
                try:
                    configure_wifi_nmcli(ssid, password)
                    connect_wifi_nmcli(ssid)
                    
                    # Add a small delay to ensure connection is established
                    time.sleep(2)
                    
                    result = subprocess.check_output(["hostname", "-I"], timeout=10)
                    ip_str = result.decode("utf-8").strip().split()[0]
                    
                    success_msg = {
                        "status": "success", 
                        "message": f"Successfully connected to {ssid}",
                        "ip_addr": ip_str
                    }
                    self.status_char.set_status(json.dumps(success_msg))
                    
                except subprocess.CalledProcessError as e:

                    stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8")
                    stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8")

                    if "psk: property is invalid" in stderr:
                        error_type = "Invalid password"
                    elif "secrets were required" in stderr or "encryption keys are required" in stdout:
                        error_type = "Incorrect password"
                    elif "network could not be found" in stderr:
                        error_type = "Network not found"
                    else:
                        error_type = "Connection failed"

                    error_msg = {
                        "status": "failed",
                        "error": error_type,
                        # "details": stderr.strip(),
                    }

                    self.status_char.set_status(json.dumps(error_msg))
                    
                except Exception as e:
                    error_msg = {
                        "status": "failed",
                        "error": "Something went wrong",
                        "details": str(e)
                    }
                    self.status_char.set_status(json.dumps(error_msg))
            
            # Start the background task
            thread = threading.Thread(target=wifi_connection_task)
            thread.daemon = True  # Dies when main thread dies
            thread.start()
            
            return value
        
        except json.JSONDecodeError as e:
            error_msg = {
                "status": "failed",
                "error": "Invalid JSON format",
                "details": str(e)
            }

            self.status_char.set_status(json.dumps(error_msg))
            return value
            
        except Exception as e:
            error_msg = {
                "status": "failed",
                "error": "WriteValue error",
                "details": str(e)
            }
            print(f"WriteValue error: {error_msg}")
            self.status_char.set_status(json.dumps(error_msg))
            return value

class writeWifiActionCharacteristic(Characteristic):
    WIFI_CONNECT_ACTION_UUID = "00000008-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service, status_char):
        Characteristic.__init__(self, self.WIFI_CONNECT_ACTION_UUID, ["write"], service)
        self.status_char = status_char

    def WriteValue(self, value, options):
        try:
            # Decode and parse JSON from value
            raw = bytes(value).decode("utf-8")
            data = json.loads(raw)

            ssid = data.get("s", "").strip()
            action = data.get("a", "").strip()

            if not ssid or not action:
                raise InvalidWifiRequest("Missing SSID or Action")

            if action not in ["add","sub","del"]:
                raise InvalidWifiRequest("Invalid Action")
            
            action_msg_res = {}

            if action == "add":
                action_msg_res["status"] = "connecting"
                action_msg_res["message"] = f"Connecting to {ssid}..."
            elif action == "sub":
                action_msg_res["status"] = "disconnecting"
                action_msg_res["message"] = f"Disconnecting from {ssid}..."
            elif action == "del":
                action_msg_res["status"] = "forgetting"
                action_msg_res["message"] = f"Forgetting {ssid}..."

            # Notify client that connection is starting
            self._safe_set_status(action_msg_res)

            # Start connection in a background thread
            threading.Thread(
                target=self._handle_task,
                args=(ssid,action),
                daemon=True
            ).start()

        except json.JSONDecodeError as e:
            self._safe_set_status({
                "status": "failed",
                "error": "Invalid JSON format",
                "details": str(e)
            })

        except InvalidWifiRequest as e:
            self._safe_set_status({
                "status": "failed",
                "error": e.message,
            })
        except Exception as e:
            self._safe_set_status({
                "status": "failed",
                "error": "WriteValue error",
                "details": str(e)
            })

    def _handle_task(self, ssid, action):
        action_msg_res = {}
        try:
            if action == "add":
                connect_wifi_nmcli(ssid)
                action_msg_res["message"] = f"Connected to {ssid}"
            elif action == "sub":
                connect_wifi_nmcli(ssid,False)
                action_msg_res["message"] = f"Disconnected from {ssid}..."
            elif action == "del":
                delete_wifi_connection(ssid)
                action_msg_res["message"] = f"Forgotten {ssid}"

            action_msg_res["status"] = "success"
            self._safe_set_status(action_msg_res)

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="ignore")
            stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="ignore")

            combined_output = (stderr + stdout).lower()

            if "cannot delete unknown connection" in combined_output:
                error_type = "Network is not saved"
            elif "is not an active connection" in combined_output or "is not an active connection" in combined_output:
                error_type = "Network is not connected"
            elif "unknown connection" in combined_output or "network could not be found" in combined_output:
                error_type = "Network not found or not in range"
            elif "device not managed" in combined_output or "not available" in combined_output:
                error_type = "Network device unavailable"
            elif "secrets were required" in combined_output or "passwords or encryption keys are required" in combined_output:
                error_type = "Retry with password or forget network"
            elif "connection activation failed" in combined_output:
                error_type = "Connection failed"
            else:
                error_type = "Connection failed"

            self._safe_set_status({
                "status": "failed",
                "error": error_type
            })

        except Exception as e:
            self._safe_set_status({
                "status": "failed",
                "error": "Something went wrong",
                "details": str(e)
            })

    def _safe_set_status(self, status_dict):
        try:
            status_json = json.dumps(status_dict)
            self.status_char.set_status(status_json)
        except Exception:
            print("Failed to set status:")

class WifiStatusCharacteristic(Characteristic):
    WIFI_STATUS_UUID = "00000004-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(self, self.WIFI_STATUS_UUID, ["read","notify"], service)
        self.value = []
        self.notifying = False

    def set_status(self, message):
        self.value = [dbus.Byte(b) for b in message.encode("utf-8")]
        if self.notifying:
            self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": self.value}, [])

    def ReadValue(self, options):
        return self.value

    def StartNotify(self):
        self.notifying = True

    def StopNotify(self):
        self.notifying = False

class GetIpAdddrCharacteristic(Characteristic):
    IP_ADDR_UUID = "00000005-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(self, self.IP_ADDR_UUID, ["read"], service)
        self.value = []

    def get_ip_addr(self):
        try:
            result = subprocess.check_output(["hostname", "-I"])
            ip_str = result.decode("utf-8").strip().split()[0]
            self.value = [dbus.Byte(c.encode()) for c in ip_str]
        except Exception as e:
            print(f"Failed to get IP address: {e}")
            self.value = []

    def ReadValue(self, options):
        self.get_ip_addr()
        return self.value

class GetMacCharacteristic(Characteristic):
    MAC_UUID = "00000006-710e-4a5b-8d75-3e5b444bc3cf"

    def __init__(self, service):
        Characteristic.__init__(self, self.MAC_UUID, ["read"], service)
        self.value = []

    def get_device_mac(self):
        try:
            ble_output = subprocess.check_output(["hciconfig"], text=True)
            match = re.search(r"BD Address: ([0-9A-F:]{17})", ble_output)
            if match:
                return {
                    "status": "success",
                    "mac": match.group(1).lower(),
                    "message": "Fetched MAC successfully.",
                }
        except subprocess.CalledProcessError:
            pass

        for iface in ["eth0", "wlan0"]:
            try:
                result = subprocess.run(
                    ["cat", f"/sys/class/net/{iface}/address"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True,
                )
                mac = result.stdout.strip()
                if mac and mac != "00:00:00:00:00:00":
                    return {
                        "status": "success",
                        "mac": mac,
                        "message": "Fetched MAC successfully.",
                    }
            except subprocess.CalledProcessError:
                continue

        return {"status": "failed", "mac": None, "message": "Failed ti fetched MAC."}

    def get_mac_addr(self):
        try:
            result = self.get_device_mac()
            mac_str = str(result.get("mac"))
            self.value = [dbus.Byte(c.encode()) for c in mac_str]
        except Exception as e:
            print(f"Failed to get IP address: {e}")
            self.value = []

    def ReadValue(self, options):
        self.get_mac_addr()
        return self.value


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
