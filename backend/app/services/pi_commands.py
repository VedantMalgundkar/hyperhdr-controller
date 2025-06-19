import re
import os
import psutil
import time
import requests
import subprocess
from .release_cache import save_to_releases_json,load_from_releases_json
from dotenv import load_dotenv

agent_process = None
ble_process = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
wifi_util_path = os.path.join(BASE_DIR, "wifi_module", "wifi_utilities.py")
ble_auto_pairing_path = os.path.join(BASE_DIR, "ble", "auto_pair_agent.py")

load_dotenv()

PAIRING_FLAG = "/home/pi/.paired"

def _get_service_status(service_name):
    result = subprocess.run(
        ["sudo", "systemctl", "is-active", service_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout.strip()

def fetch_github_versions():
    """Fetch HyperHDR releases from GitHub with version, description, and Raspberry Pi 64-bit .deb download link."""
    
    CACHE_TTL = 24 * 60 * 60
    current_time = time.time()
    res = load_from_releases_json()

    ver_res = {}
    try:
        ver_res = get_hyperhdr_version()
    except Exception as e:
        ver_res = {
            "status":"failed",
            "version": None,
            "error": f"Command failed: {str(e)}",
        }
    version_tag = f"v{ver_res.get('version')}"

    res["releases"] = [
        {**release, "is_installed": release.get("version") == version_tag}
        for release in res["releases"]
    ]
    
    if res and "created_at" in res and (current_time - res["created_at"]) < CACHE_TTL:
        return {"status": "success","message":"Version fetched successfully", "versions": res["releases"]}

    response = requests.get(
        os.getenv("HYPERHDR_REPO"),
        timeout=5
    )
    response.raise_for_status()

    releases = response.json()
    result = []

    for release in releases:
        version = release.get("tag_name")
        if "beta" in version:
            continue
        name = release.get("name")
        published_at = release.get("published_at")
        assets = release.get("assets", [])
        filterted_assets = []

        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".deb") and ("aarch64" in name or "arm64" in name):
                filterted_assets.append({
                    "name":asset.get("name",""),
                    "size":asset.get("size",""),
                    "download_count":asset.get("download_count",""),
                    "browser_download_url":asset.get("browser_download_url",""),
                    "created_at":asset.get("created_at",""),
                    "updated_at":asset.get("updated_at","")
                    })
        
        if len(filterted_assets) == 0:
            continue
        
        filterted_assets.sort(key=lambda x: "bookworm" not in x["name"].lower())
        
        result.append({
            "version": version,
            "name":name,
            "published_at":published_at,
            "assets": filterted_assets,
            "is_installed": f"v{ver_res.get('version')}" == version
        })

    save_to_releases_json({
        "releases": result,
        "created_at": current_time
    })
    
    return {"status": "success","message":"Version fetched successfully", "versions": result }

def get_hyperhdr_version():
    result = subprocess.run(
        ["hyperhdr", "--version"],
        capture_output=True,
        text=True,
        check=True
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
        capture_output=True, text=True
    )
    return {"status":"success", "message": "Service started successfully."}

def stop_hyperhdr_service(username):
    subprocess.run(["sudo", "systemctl", "stop", f"hyperhdr@{username}.service"], check=True)
    return {"status":"success","message": "Service stopped successfully."}

def status_hyperhdr_service(username):
    result = _get_service_status(f"hyperhdr@{username}.service")
    return {"status": "success","hyperhdr_status": result, "message": "Fetched hyperhdr status successfully"}

def uninstall_current_hyper_hdr_service():
    subprocess.run(
        ["sudo", "dpkg", "-r", "hyperhdr"],
        check=True,
        capture_output=True,
        text=True
    )
    return {"status":"success", "message": "Current hyperhdr unistalled successfully."}

def is_paired():
    return os.path.exists(PAIRING_FLAG)

def mark_paired():
    with open(PAIRING_FLAG, "w") as f:
        f.write(str(time.time()))

def start_hotspot(ssid='Pi-Hotspot', password='raspberry123', interface='wlan0'):
    try:
        # Check if NetworkManager is active
        subprocess.run(["nmcli", "general", "status"], check=True, stdout=subprocess.PIPE)

        # Start the hotspot
        result = subprocess.run(
            ["sudo", "nmcli", "device", "wifi", "hotspot", f"ifname", interface, f"ssid", ssid, f"password", password],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "error", "error": e.stderr}

def stop_hotspot():
    # Get list of active connections
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"],
        check=True, stdout=subprocess.PIPE, text=True
    )
    active_connections = result.stdout.strip().split('\n')

    # Look for the Hotspot connection
    for conn in active_connections:
        name, conn_type = conn.split(':')
        if name.lower() == 'hotspot':
            # Bring down the hotspot connection
            subprocess.run(["sudo", "nmcli", "con", "down", name], check=True)
            return {"status": "success", "message": f"Hotspot '{name}' stopped."}

    return {"status": "error", "message": "No active hotspot found."}

def configure_wifi_nmcli(ssid: str, password: str):
    # Add or update the connection profile
    subprocess.run([
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


def connect_wifi_nmcli(ssid:str):
    # Immediately activate the connection
    try:
        return subprocess.run([
            "sudo", "nmcli", "connection", "up", ssid
        ], check=True)
    except subprocess.CalledProcessError as e:
        return {"status":"failed", "error": "Wi-Fi connection failed", "details": e.stderr}


def scan_wifi_around():
    output = subprocess.check_output(
        ["sudo", "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "dev", "wifi", "list"]
    ).decode("utf-8")

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

    return {"status":"success", "message":"Network fetched successfully", "networks": networks}

def is_ble_active():
    ble_status = _get_service_status('auto_pair_agent.service')
    wifi_status = _get_service_status('wifi_utilities.service')

    if ble_status == "active" and wifi_status == "active":
        return {
            "status": "success",
            "ble_status": "active",
            "message": "BLE services are running."
        }
    else:
        return {
            "status": "success",
            "ble_status": "inactive",
            "message": "One or both BLE services are not running.",
            "details": {
                "auto_pair_agent": ble_status,
                "wifi_utilities": wifi_status
            }
        }

def start_ble_service():
    res = is_ble_active()
    if res["ble_status"] == "active":
        return {
            "status": "success",
            "message": "BLE services already running."
        }

    subprocess.run(['sudo', 'systemctl', 'start', 'auto_pair_agent.service'])
    subprocess.run(['sudo', 'systemctl', 'start', 'wifi_utilities.service'])

    return {
        "status": "success",
        "message": "BLE services started successfully."
    }

def stop_ble_service():
    res = is_ble_active()
    if res["ble_status"] != "active":
        return {
            "status": "success",
            "message": "BLE services are already stopped."
        }

    subprocess.run(['sudo', 'systemctl', 'stop', 'wifi_utilities.service'])
    subprocess.run(['sudo', 'systemctl', 'stop', 'auto_pair_agent.service'])

    return {
        "status": "success",
        "message": "BLE services stopped successfully."
    }

def reset_service():
    subprocess.run(
        ["sudo", "dpkg", "--purge", "hyperhdr"],
        check=True,
        capture_output=True,
        text=True
    )

    subprocess.run(
        ["sudo", "apt", "autoremove", "-y"],
        check=True,
        capture_output=True,
        text=True
    )

    subprocess.run(["sudo", "rm", "-rf", "/etc/hyperhdr"], check=False)
    subprocess.run(["sudo", "rm", "-rf", "/opt/hyperhdr"], check=False)
    subprocess.run(["sudo", "rm", "-rf", "/var/lib/hyperhdr"], check=False)
    subprocess.run(["sudo", "rm", "-f", "/etc/systemd/system/hyperhdr.service"], check=False)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=False)

    return {
        "status": "success",
        "message": "HyperHDR fully uninstalled and orphaned packages removed."
    }
