import re
import os
import psutil
import time
import requests
import subprocess
from .hyperhdr_history import save_to_releases_json,load_from_releases_json
from dotenv import load_dotenv

agent_process = None
ble_process = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
wifi_util_path = os.path.join(BASE_DIR, "wifi_module", "wifi_utilities.py")
ble_auto_pairing_path = os.path.join(BASE_DIR, "ble", "auto_pair_agent.py")

load_dotenv()

PAIRING_FLAG = "/home/pi/.paired"

def fetch_github_versions():
    """Fetch HyperHDR releases from GitHub with version, description, and Raspberry Pi 64-bit .deb download link."""
    
    CACHE_TTL = 24 * 60 * 60
    current_time = time.time()
    res = load_from_releases_json()
    
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
        description = release.get("body", "")
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
        
        result.append({
            "version": version,
            "name":name,
            "description":description,
            "published_at":published_at,
            "description": description,
            "assets": filterted_assets
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
    result = subprocess.run(
        ["sudo", "systemctl", "is-active", f"hyperhdr@{username}.service"], 
        capture_output=True, text=True
    )
    status = result.stdout.strip()
    return {"status": "success","hyperhdr_status":status, "message": "Fetched hyperhdr status successfully"}

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
                    "in_use": in_use
                })

    networks = sorted(networks,key=lambda x:x["in_use"],reverse=True)

    return {"status":"success", "message":"Network fetched successfully", "networks": networks}


# def start_ble_service():
#     global ble_process, agent_process
#     if ble_process is None or ble_process.poll() is not None:
#         agent_process = subprocess.Popen(["/usr/bin/python3", ble_auto_pairing_path])
#         ble_process = subprocess.Popen(["/usr/bin/python3", wifi_util_path])
#         return {"status":"success", "message": "BLE started successfully."}
#     return {"status":"success", "message": "BLE already running"}

# def stop_ble_service():
#     global ble_process, agent_process
#     if ble_process and ble_process.poll() is None:
#         if agent_process and agent_process.poll() is None:
#             agent_process.terminate()
#             agent_process = None
#         ble_process.terminate()
#         ble_process = None
#         return {"status":"success", "message": "BLE stopped successfully."}
#     return {"status":"success", "message": "BLE is not running"}

def find_process_by_script(script_path):
    """Return a list of psutil.Process objects matching the script path."""
    matching = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and script_path in ' '.join(cmdline):
                matching.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return matching

def start_ble_service():
    wifi_processes = find_process_by_script(wifi_util_path)
    agent_processes = find_process_by_script(ble_auto_pairing_path)

    if not wifi_processes:
        subprocess.Popen(["/usr/bin/python3", ble_auto_pairing_path])
        subprocess.Popen(["/usr/bin/python3", wifi_util_path])
        return {"status": "success", "message": "BLE started successfully."}
    else:
        return {"status": "success", "message": "BLE already running."}

def stop_ble_service():
    stopped_any = False

    for proc in find_process_by_script(wifi_util_path) + find_process_by_script(ble_auto_pairing_path):
        try:
            proc.terminate()
            stopped_any = True
        except Exception as e:
            return {"status": "error", "message": f"Failed to stop BLE: {e}"}

    return {
        "status": "success",
        "message": "BLE stopped successfully." if stopped_any else "BLE is not running."
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
