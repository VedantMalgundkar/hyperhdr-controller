from flask import Blueprint, jsonify, abort
import subprocess
from flask import request
from app.utils.req_modifier import modify_request, get_current_user
from app.utils.hyperhdr_version_info import scan_wifi_around, stop_hotspot, configure_wifi_nmcli, connect_wifi_nmcli, start_hyperhdr_service,stop_hyperhdr_service,status_hyperhdr_service,get_hyperhdr_version,fetch_github_versions
from pydantic import BaseModel, SecretStr, ValidationError

class WifiRequest(BaseModel):
    ssid: str  # Wi-Fi network name (string)
    password: str  #SecretStr  # Password (stored securely)

main_bp = Blueprint('main', __name__)

@main_bp.route('/start-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def start_hyperhdr():
    username = request.custom_data['user']
    res = start_hyperhdr_service(username)
    if res.get('error'):
        return jsonify(res),500
    return jsonify(res),200


@main_bp.route('/stop-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def stop_hyperhdr():
    username = request.custom_data['user']
    res = stop_hyperhdr_service(username)
    if res.get('error'):
        return jsonify(res),500
    return jsonify(res),200

@main_bp.route('/status-hyperhdr', methods=['GET'])
@modify_request(add_data={"user": get_current_user()})
def status_hyperhdr():
    username = request.custom_data['user']
    res = status_hyperhdr_service(username)
    if res.get('error'):
        return jsonify(res),500
    return jsonify(res),200

@main_bp.route("/hyperhdr/current-version", methods=["GET"])
def get_current_hyperhdr_version():
    try:
        local_version = get_hyperhdr_version()
        
        return jsonify(local_version),200
    except Exception as e:
        return jsonify({
            "version": None,
            "output": f"Command failed: {str(e)}"
        }), 500

@main_bp.route("/hyperhdr/avl-versions", methods=["GET"])
def get_hyperhdr_versions():
    try:
        github_versions = fetch_github_versions()

        return jsonify(github_versions), 200
    except Exception as e:
        return jsonify({"error": f"Error checking status: {str(e)}"}), 500

@main_bp.route("/connect-wifi", methods=["POST"])
def connect_wifi():
    if not request.is_json:
        return jsonify({
            "error": "Unsupported Media Type",
            "details": "Content-Type must be application/json"
        }), 415

    try:
        json_data = request.get_json()
        
        req = WifiRequest(**json_data)
        res = configure_wifi_nmcli(req.ssid, req.password)

        stop_hotspot()

        print("\n  hotspot stopped >>>>>>>>>> \n")

        connect_wifi_nmcli(req.ssid)

        print(f"\n  connected to {req.ssid} >>>>>>>>>> \n")

        return jsonify({"success":"true", "details": f"Connected to Wi-Fi {req.ssid}"})

    except ValidationError as e:
        return jsonify({"success":"false", "error": "Invalid data", "details": str(e)}), 400
    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        return jsonify({"success":"false", "error": "Server error", "details": str(e)}), 500

@main_bp.route("/scan-wifi", methods=["GET"])
def scan_wifi():
    try:
        available_network = scan_wifi_around()
        return jsonify({"success":"true", "networks": available_network})

    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        return jsonify({"success":"false", "error": "Server error", "details": str(e)}), 500

