import re
import os
import time
import requests
import subprocess
from .hyperhdr_history import save_to_releases_json,load_from_releases_json
from dotenv import load_dotenv

load_dotenv()

PAIRING_FLAG = "/home/pi/.paired"

def fetch_github_versions():
    """Fetch HyperHDR releases from GitHub with version, description, and Raspberry Pi 64-bit .deb download link."""
    
    CACHE_TTL = 24 * 60 * 60
    current_time = time.time()
    res = load_from_releases_json()
    
    if res and "created_at" in res and (current_time - res["created_at"]) < CACHE_TTL:
        return res["releases"]

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
    
    return result


def get_hyperhdr_version():
    try:
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
            "version": version,
            "output": full_output
        }
    except subprocess.CalledProcessError as e:
        return {
            "version": None,
            "output": e.stderr.strip() if e.stderr else "Failed to get version"
        }
    except FileNotFoundError:
        return {
            "version": None,
            "output": "HyperHDR is not installed or not in PATH"
        }

def start_hyperhdr_service(username):
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "start", f"hyperhdr@{username}.service"], 
            capture_output=True, text=True
        )
        return {"message": "Service started successfully."}
    except subprocess.CalledProcessError as e:
        return {"error": f"Error checking status: {str(e)}"}

def stop_hyperhdr_service(username):
    try:
        subprocess.run(["sudo", "systemctl", "stop", f"hyperhdr@{username}.service"], check=True)
        return {"message": "Service stopped successfully."}
    except subprocess.CalledProcessError as e:
        return {"error": f"Failed to stop service: {str(e)}"}

def status_hyperhdr_service(username):
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", f"hyperhdr@{username}.service"], 
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        return {"status": status}
    except subprocess.CalledProcessError as e:
        return {"error": f"Error checking status: {str(e)}"}

def uninstall_current_hyper_hdr_service():
    try:
        subprocess.run(
            ["sudo", "dpkg", "-r", "hyperhdr"],
            check=True,
            capture_output=True,
            text=True
        )
        return {"message": "Current hyperhdr unistalled successfully."}
    except subprocess.CalledProcessError as e:
        return {"error": f"Could not uninstall existing version: {e.stderr}"}

def is_paired():
    return os.path.exists(PAIRING_FLAG)

def mark_paired():
    with open(PAIRING_FLAG, "w") as f:
        f.write(str(time.time()))

def start_hotspot():
    subprocess.run(["sudo", "systemctl", "start", "dnsmasq"], check=True)
    subprocess.run(["sudo", "systemctl", "start", "hostapd"], check=True)

def stop_hotspot():
    subprocess.run(["sudo", "systemctl", "stop", "hostapd"], check=True)
    subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], check=True)

def connect_wifi_nmcli(ssid: str, password: str):
    # Add or update the connection profile
    subprocess.run([
        "sudo", "nmcli", "connection", "add",
        "type", "wifi",
        "con-name", ssid,
        "ssid", ssid,
        "ifname", "wlan0",
        "wifi-sec.key-mgmt", "wpa-psk",
        "wifi-sec.psk", password,
        "connection.autoconnect", "yes",  # Auto-reconnect on reboot
        "--", "save", "yes"
    ], check=True)

    # Immediately activate the connection
    subprocess.run([
        "sudo", "nmcli", "connection", "up", ssid
    ], check=True)