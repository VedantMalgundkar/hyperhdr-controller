import re
import os
import psutil
import time
import requests
import subprocess
from collections import defaultdict
from .release_cache import save_to_releases_json, load_from_releases_json
from dotenv import load_dotenv

agent_process = None
ble_process = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
wifi_util_path = os.path.join(BASE_DIR, "wifi_module", "wifi_utilities.py")
ble_auto_pairing_path = os.path.join(BASE_DIR, "ble", "auto_pair_agent.py")

load_dotenv()

PAIRING_FLAG = "/home/pi/.paired"


def _get_service_status(service_name, type="status"):
    cmd = "is-active" if type == "status" else "is-enabled"
    result = subprocess.run(
        ["sudo", "systemctl", cmd, service_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def fetch_github_versions(fetch_bookworm: bool = False):
    """Fetch HyperHDR releases with architecture- and Bookworm-aware filtering."""

    CACHE_TTL = 24 * 60 * 60
    current_time = time.time()
    res = load_from_releases_json()

    try:
        ver_res = get_hyperhdr_version()
    except Exception as e:
        ver_res = {
            "status": "failed",
            "version": None,
            "error": f"Command failed: {str(e)}",
        }

    if res:
        if "created_at" in res and (current_time - res["created_at"]) < CACHE_TTL:
            return {
                "status": "success",
                "message": "Version fetched successfully",
                "versions": res["releases"],
            }

    response = requests.get(os.getenv("HYPERHDR_REPO"), timeout=5)
    response.raise_for_status()

    releases = response.json()
    grouped = defaultdict(list)

    for release in releases:
        tag_name = release.get("tag_name", "")
        if "beta" in tag_name.lower():
            continue

        for asset in release.get("assets", []):
            asset_name = asset.get("name", "").lower()

            if not asset_name.endswith(".deb"):
                continue
            if "arm64" not in asset_name and "aarch64" not in asset_name:
                continue

            grouped[tag_name].append(
                {
                    "id": str(asset.get("id", "")),
                    "file_name": asset.get("name", ""),
                    "size": str(asset.get("size", "")),
                    "download_count": str(asset.get("download_count", "")),
                    "browser_download_url": asset.get("browser_download_url", ""),
                    "created_at": asset.get("created_at", ""),
                    "updated_at": asset.get("updated_at", ""),
                    "tag_name": tag_name,
                    "release_name": release.get("name", ""),
                    "is_installed": f"v{ver_res.get('version')}" == tag_name,
                }
            )

    result = []

    for tag, assets in grouped.items():
        has_bookworm = any("bookworm" in a["file_name"].lower() for a in assets)

        if not has_bookworm:
            result.extend(assets)
        else:
            for asset in assets:
                is_bookworm = "bookworm" in asset["file_name"].lower()

                if fetch_bookworm and is_bookworm:
                    result.append(asset)
                elif not fetch_bookworm and not is_bookworm:
                    result.append(asset)

    save_to_releases_json({"releases": result, "created_at": current_time})

    return {
        "status": "success",
        "message": "Version fetched successfully",
        "versions": result,
    }


def get_system_info():
    command = "uname -m && (cat /etc/os-release || cat /etc/*release || lsb_release -a)"
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, check=True
    )

    output = result.stdout.strip().splitlines()

    data = {}
    if output:
        # First line is architecture
        data["ARCH"] = output[0].strip()

        # Remaining lines are OS info
        for line in output[1:]:
            if "=" in line:
                key, val = line.split("=", 1)
                data[key.strip()] = val.strip().strip('"')
            elif ":" in line:
                key, val = line.split(":", 1)
                data[key.strip().upper()] = val.strip()

    return {
        "status": "success",
        "message": "Fetched system info successfully",
        "data": data,
    }


def get_hyperhdr_version():
    result = subprocess.run(
        ["hyperhdr", "--version"], capture_output=True, text=True, check=True
    )
    full_output = result.stdout.strip()

    # Extract version using regex
    version_match = re.search(r"Version\s*:\s*([\d.]+)", full_output)
    version = version_match.group(1) if version_match else None

    return {
        "status": "success",
        "message": f"Fetched hyperhdr version successfully : {full_output}",
        "version": version,
    }


def start_hyperhdr_service(username):
    result = subprocess.run(
        ["sudo", "systemctl", "start", f"hyperhdr@{username}.service"],
        capture_output=True,
        text=True,
    )
    return {"status": "success", "message": "Service started successfully."}


def stop_hyperhdr_service(username):
    subprocess.run(
        ["sudo", "systemctl", "stop", f"hyperhdr@{username}.service"], check=True
    )
    return {"status": "success", "message": "Service stopped successfully."}


def status_hyperhdr_service(username):
    result = _get_service_status(f"hyperhdr@{username}.service")
    return {
        "status": "success",
        "hyperhdr_status": result,
        "message": "Fetched hyperhdr status successfully",
    }


def enable_hyperhdr_service_on_boot(username):
    subprocess.run(
        ["sudo", "systemctl", "enable", f"hyperhdr@{username}.service"], check=True
    )
    return {"status": "success", "message": "Service enabled on boot successfully."}


def disable_hyperhdr_service_on_boot(username):
    subprocess.run(
        ["sudo", "systemctl", "disable", f"hyperhdr@{username}.service"], check=True
    )
    return {"status": "success", "message": "Service disabled from boot successfully."}


def boot_status_hyperhdr_service(username):
    status = _get_service_status(f"hyperhdr@{username}.service", type="boot")
    return {
        "status": "success",
        "is_enabled_on_boot": status == "enabled",
        "boot_status": status,
        "message": "Fetched boot status successfully.",
    }


def uninstall_current_hyper_hdr_service():
    subprocess.run(
        ["sudo", "dpkg", "-r", "hyperhdr"], check=True, capture_output=True, text=True
    )
    return {"status": "success", "message": "Current hyperhdr unistalled successfully."}


def is_paired():
    return os.path.exists(PAIRING_FLAG)


def mark_paired():
    with open(PAIRING_FLAG, "w") as f:
        f.write(str(time.time()))


def start_hotspot(ssid="Pi-Hotspot", password="raspberry123", interface="wlan0"):
    try:
        # Check if NetworkManager is active
        subprocess.run(
            ["nmcli", "general", "status"], check=True, stdout=subprocess.PIPE
        )

        # Start the hotspot
        result = subprocess.run(
            [
                "sudo",
                "nmcli",
                "device",
                "wifi",
                "hotspot",
                f"ifname",
                interface,
                f"ssid",
                ssid,
                f"password",
                password,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "error": e.stderr}


def stop_hotspot():
    # Get list of active connections
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    active_connections = result.stdout.strip().split("\n")

    # Look for the Hotspot connection
    for conn in active_connections:
        name, conn_type = conn.split(":")
        if name.lower() == "hotspot":
            # Bring down the hotspot connection
            subprocess.run(["sudo", "nmcli", "con", "down", name], check=True)
            return {"status": "success", "message": f"Hotspot '{name}' stopped."}

    return {"status": "error", "message": "No active hotspot found."}


def get_connected_network():
    ssid = (
        subprocess.check_output(
            "nmcli -t -f active,ssid,signal,security dev wifi | grep '^yes' | cut -d':' -f2-",
            shell=True,
        )
        .decode("utf-8")
        .strip()
    )

    if not ssid:
        return {"status": "success", "message": "No connected network", "network": None}

    parts = ssid.split(":", maxsplit=2)
    return {
        "status": "success",
        "message": "Connected network fetched successfully",
        "network": {
            "ssid": parts[0],
            "signal": int(parts[1]),
            "security": parts[2] if len(parts) > 2 else "OPEN",
            "in_use": True,
            "is_saved": True,
        },
    }


def is_ble_active():
    ble_status = _get_service_status("auto_pair_agent.service")
    wifi_status = _get_service_status("wifi_utilities.service")

    if ble_status == "active" and wifi_status == "active":
        return {
            "status": "success",
            "ble_status": "active",
            "message": "BLE services are running.",
        }
    else:
        return {
            "status": "success",
            "ble_status": "inactive",
            "message": "One or both BLE services are not running.",
            "details": {"auto_pair_agent": ble_status, "wifi_utilities": wifi_status},
        }


def start_ble_service():
    res = is_ble_active()
    if res["ble_status"] == "active":
        return {"status": "success", "message": "BLE services already running."}

    subprocess.run(["sudo", "systemctl", "start", "auto_pair_agent.service"])
    subprocess.run(["sudo", "systemctl", "start", "wifi_utilities.service"])

    return {"status": "success", "message": "BLE services started successfully."}


def stop_ble_service():
    res = is_ble_active()
    if res["ble_status"] != "active":
        return {"status": "success", "message": "BLE services are already stopped."}

    subprocess.run(["sudo", "systemctl", "stop", "wifi_utilities.service"])
    subprocess.run(["sudo", "systemctl", "stop", "auto_pair_agent.service"])

    return {"status": "success", "message": "BLE services stopped successfully."}


def get_device_mac():
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


def set_hostname(hostname):
    result = subprocess.run(
        ["sudo", "hostnamectl", "set-hostname", hostname],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    subprocess.run(
        [
            "sudo",
            "sed",
            "-i",
            f"s/^127\\.0\\.1\\.1[[:space:]]\\+.*/127.0.1.1       {hostname}/",
            "/etc/hosts",
        ],
        check=True,
    )

    return {
        "status": "success",
        "message": f"Hostname set to '{hostname}'.",
        "details": result.stdout.strip() or result.stderr.strip(),
    }


def restart_systemctl_service(service):
    subprocess.run(
        ["sudo", "systemctl", "restart", service],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {"status": "success", "message": f"{service} restarted successfully."}


def reset_service():
    subprocess.run(
        ["sudo", "dpkg", "--purge", "hyperhdr"],
        check=True,
        capture_output=True,
        text=True,
    )

    subprocess.run(
        ["sudo", "apt", "autoremove", "-y"], check=True, capture_output=True, text=True
    )

    subprocess.run(["sudo", "rm", "-rf", "/etc/hyperhdr"], check=False)
    subprocess.run(["sudo", "rm", "-rf", "/opt/hyperhdr"], check=False)
    subprocess.run(["sudo", "rm", "-rf", "/var/lib/hyperhdr"], check=False)
    subprocess.run(
        ["sudo", "rm", "-f", "/etc/systemd/system/hyperhdr.service"], check=False
    )
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)

    return {
        "status": "success",
        "message": "HyperHDR fully uninstalled and orphaned packages removed.",
    }
