from flask import Blueprint, jsonify
from pydantic import BaseModel
import subprocess
import requests
import os
import time
from flask import request
from app.utils.req_modifier import modify_request, get_current_user
from app.utils.hyperhdr_version_info import get_hyperhdr_version, status_hyperhdr_service, stop_hyperhdr_service,uninstall_current_hyper_hdr_service

hyperhdr_install_bp = Blueprint('hyperhdr_install', __name__)

DOWNLOAD_DIR = "/tmp/hyperhdr_debs"
LOCK_FILE = "/tmp/hyperhdr_install.lock"

class InstallRequest(BaseModel):
    url: str  # Full GitHub asset URL like `.bookworm-aarch64.deb`

def is_installation_in_progress():
    return os.path.exists(LOCK_FILE)

def set_installation_lock():
    with open(LOCK_FILE, "w") as f:
        f.write(str(time.time()))  # optional: write timestamp

def clear_installation_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

def cleanup_downloads():
    """Remove all .deb files from download directory"""
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            if filename.endswith('.deb'):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                try:
                    os.remove(filepath)
                except Exception as e:
                    print(f"Warning: Could not remove {filepath}: {e}")

@hyperhdr_install_bp.post("/install-hyperhdr")
@modify_request(add_data={"user": get_current_user()})
def install_hyperhdr():
    json_data = request.get_json(silent=True) or {}
    if not json_data:
        return jsonify({"error": "No JSON data provided"}), 400
        
    req = InstallRequest(**json_data)
    username = request.custom_data['user']

    if is_installation_in_progress():
        raise HTTPException(status_code=429, detail="Installation already in progress.")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = json_data["url"].split("/")[-1]
    filepath = os.path.join(DOWNLOAD_DIR, filename)

    try:
        set_installation_lock()

        # Download file
        try:
            with requests.get(json_data["url"], stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {e}")
    
        curr_ver = get_hyperhdr_version()

        if curr_ver['version']:
            
            status_res = status_hyperhdr_service(username)
            if not status_res.get('error') and status_res['status'] == 'active':
                stop_res = stop_hyperhdr_service(username)
                print(stop_res)

            unins_res = uninstall_current_hyper_hdr_service()
            if unins_res.get("error"):
                raise HTTPException(status_code=500, detail=unins_res.error)
            print(unins_res)

        # Install package
        try:
            result = subprocess.run(
                ["sudo", "dpkg", "-i", filepath],
                check=True,
                capture_output=True,
                text=True
            )
            return {"message": "Installation complete", "stdout": result.stdout}
        except subprocess.CalledProcessError as e:
            raise HTTPException(status_code=500, detail=f"Install failed: {e.stderr}")

    finally:
        try:
            # Remove the downloaded .deb file
            if os.path.exists(filepath):
                os.remove(filepath)
            # Optional: Clean up any other old .deb files
            cleanup_downloads()
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")
        finally:
            clear_installation_lock()