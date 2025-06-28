import time
from flask import Blueprint, jsonify
from pydantic import BaseModel
import subprocess
import requests
import os
import time
import fcntl
from contextlib import contextmanager
from flask import request
from werkzeug.exceptions import TooManyRequests, HTTPException
from app.middlewares.req_modifier import modify_request, get_current_user
from app.services.pi_commands import (
    get_hyperhdr_version,
    status_hyperhdr_service,
    stop_hyperhdr_service,
    uninstall_current_hyper_hdr_service,
    fetch_github_versions,
)

hyperhdr_install_bp = Blueprint("hyperhdr_install", __name__)

DOWNLOAD_DIR = "/tmp/hyperhdr_debs"
LOCK_FILE = "/tmp/hyperhdr_install.lock"


class InstallRequest(BaseModel):
    url: str


@contextmanager
def file_lock(lock_path):
    """Atomic file lock with proper HTTPException handling"""
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    lock_file = open(lock_path, "w")

    try:
        # Try to acquire lock
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            raise TooManyRequests("Installation already in progress")

        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
    finally:
        # Cleanup resources
        lock_file.close()
        try:
            os.remove(lock_path)
        except:
            pass


def cleanup_downloads():
    """Remove all .deb files from download directory"""
    if os.path.exists(DOWNLOAD_DIR):
        for filename in os.listdir(DOWNLOAD_DIR):
            if filename.endswith(".deb"):
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
        return jsonify({"status": "failed", "error": "No JSON data provided"}), 400

    req = InstallRequest(**json_data)
    username = request.custom_data["user"]

    try:
        with file_lock(LOCK_FILE):
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            filename = json_data["url"].split("/")[-1]
            filepath = os.path.join(DOWNLOAD_DIR, filename)

            try:
                with requests.get(json_data["url"], stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(filepath, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
            except Exception as e:
                return jsonify({"status": "failed", "error": "Download failed"}), 500

            curr_ver = {}
            try:
                curr_ver = get_hyperhdr_version()
            except FileNotFoundError:
                curr_ver = {
                    "status": "failed",
                    "error": "HyperHDR is not installed or not in PATH",
                }

            status_res = status_hyperhdr_service(username)

            if status_res["hyperhdr_status"] == "active":
                stop_res = stop_hyperhdr_service(username)

            if curr_ver.get("status") == "success":
                unins_res = uninstall_current_hyper_hdr_service()

            # Install package
            result = subprocess.run(
                ["sudo", "dpkg", "-i", filepath],
                check=True,
                capture_output=True,
                text=True,
            )
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": "Installation complete",
                        "stdout": result.stdout,
                    }
                ),
                200,
            )

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "failed", "error": e.stderr.strip()}), 500
    except HTTPException as e:
        return jsonify({"status": "failed", "error": e.description}), e.code
    except Exception as e:
        return (
            jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}),
            500,
        )
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            cleanup_downloads()
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")


@hyperhdr_install_bp.route("/current-version", methods=["GET"])
def get_current_hyperhdr_version():
    try:
        local_version = get_hyperhdr_version()

        return jsonify(local_version), 200
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "failed",
                    "version": None,
                    "error": f"Command failed: {str(e)}",
                }
            ),
            500,
        )


@hyperhdr_install_bp.route("/avl-versions", methods=["GET"])
def get_hyperhdr_versions():
    try:
        github_versions = fetch_github_versions()

        return jsonify(github_versions), 200
    except Exception as e:
        return (
            jsonify({"success": "failed", "error": f"Error checking status: {str(e)}"}),
            500,
        )
