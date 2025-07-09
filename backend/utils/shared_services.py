import re
import subprocess

def configure_wifi_nmcli(ssid: str, password: str):
    # Add or update the connection profile
    res = subprocess.run(
        [
            "sudo",
            "nmcli",
            "connection",
            "add",
            "type",
            "wifi",
            "con-name",
            ssid,
            "ssid",
            ssid,
            "ifname",
            "wlan0",
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            password,
            "connection.autoconnect",
            "yes",
            "--",
            "save",
            "yes",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "status": "success",
        "message": res.stdout.strip()
    }

def connect_wifi_nmcli(ssid: str,connect: bool = True):
    action = "up" if connect else "down"
    res = subprocess.run(
        ["sudo", "nmcli", "connection", action , ssid],
        check=True,
        capture_output=True,
        text=True
    )
    return {
        "status": "success",
        "message": res.stdout.strip()
    }

def scan_wifi_around():
    output = subprocess.check_output(
        [
            "sudo",
            "nmcli",
            "-t",
            "-f",
            "SSID,SIGNAL,SECURITY,IN-USE",
            "dev",
            "wifi",
            "list",
        ]
    ).decode("utf-8")

    # Get list of saved (known) connections
    saved_output = subprocess.check_output(
        ["nmcli", "-t", "-f", "NAME", "connection", "show"]
    ).decode("utf-8")

    saved_ssids = set(
        [line.strip() for line in saved_output.strip().split("\n") if line.strip()]
    )

    networks = []
    pattern = re.compile(r"^(.*?):(\d+):([^:]*):?(.*)?$")

    for line in output.strip().split("\n"):
        match = pattern.match(line.strip())
        if match:
            ssid = match.group(1).strip()
            signal = int(match.group(2).strip())
            security = match.group(3).strip() or "OPEN"
            in_use_field = match.group(4).strip()
            in_use = 1 if in_use_field == "*" else 0

            if ssid:  # skip hidden/empty SSIDs
                networks.append(
                    {
                        "s": ssid,
                        "sr": signal,
                        "lck": 1 if security != "OPEN" else 0,
                        "u": in_use,
                        "sav": 1 if ssid in saved_ssids else 0,
                    }
                )

    networks = sorted(networks, key=lambda x: x["u"], reverse=True)
    return {
        "status": "success",
        "message": "Network fetched successfully",
        "networks": networks,
    }

def delete_wifi_connection(connection_name: str) -> bool:
    result = subprocess.run(
        ['sudo', 'nmcli', 'connection', 'delete', connection_name],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return True