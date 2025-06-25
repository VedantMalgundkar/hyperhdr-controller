from flask import Blueprint, jsonify, abort
import subprocess
from flask import request
from werkzeug.exceptions import HTTPException, Unauthorized, NotFound
from app.middlewares.req_modifier import modify_request, get_current_user
from app.services.pi_commands import start_ble_service, stop_ble_service, enable_hyperhdr_service_on_boot, disable_hyperhdr_service_on_boot , boot_status_hyperhdr_service, scan_wifi_around, get_connected_network , stop_hotspot, start_hotspot, configure_wifi_nmcli, connect_wifi_nmcli, start_hyperhdr_service,stop_hyperhdr_service,status_hyperhdr_service,get_hyperhdr_version, get_device_mac, set_hostname, restart_avahi_daemon  
from pydantic import BaseModel, SecretStr, ValidationError

class WifiRequest(BaseModel):
    ssid: str  # Wi-Fi network name (string)
    password: str  #SecretStr  # Password (stored securely)

main_bp = Blueprint('main', __name__)

@main_bp.route('/start-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def start_hyperhdr():
    try:
        username = request.custom_data['user']
        res = start_hyperhdr_service(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/enable-boot-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def enable_boot_hyperhdr():
    try:
        username = request.custom_data['user']
        res = enable_hyperhdr_service_on_boot(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/stop-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def stop_hyperhdr():
    try:
        username = request.custom_data['user']
        res = stop_hyperhdr_service(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/disable-boot-hyperhdr', methods=['POST'])
@modify_request(add_data={"user": get_current_user()})
def disable_boot_hyperhdr():
    try:
        username = request.custom_data['user']
        res = disable_hyperhdr_service_on_boot(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/status-hyperhdr', methods=['GET'])
@modify_request(add_data={"user": get_current_user()})
def status_hyperhdr():
    try:
        username = request.custom_data['user']
        res = status_hyperhdr_service(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/boot-status-hyperhdr', methods=['GET'])
@modify_request(add_data={"user": get_current_user()})
def boot_status_hyperhdr():
    try:
        username = request.custom_data['user']
        res = boot_status_hyperhdr_service(username)
        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route('/set-unique-hostname', methods=['POST'])
def set_unique_hostname():
    if not request.is_json:
        return jsonify({
            "status": "failed",
            "error": "Unsupported Media Type",
            "details": "Content-Type must be application/json"
        }), 415

    try:
        json_data = request.get_json()

        hostname = json_data.get("hostname").strip()
        if not hostname:
            raise NotFound(description="Missing 'hostname' in request body")

        mac = get_device_mac()

        if mac is None:
            raise RuntimeError("MAC address could not be determined from any interface")
        
        mac_suffix = mac.replace(":", "")[-5:]
        new_hostname = f"{hostname}-{mac_suffix}"

        res = set_hostname(new_hostname)

        restart_avahi_daemon()

        return jsonify(res),200
    except subprocess.CalledProcessError as e:
        return jsonify({
                "status":"failed", 
                "error": f"command failed : {str(e)}"
            }), 500
    except Exception as e:     
        return jsonify({
                "status":"failed", 
                "error": f"Unexpected error: {str(e)}"
            }), 500

@main_bp.route("/connect-wifi", methods=["POST"])
def connect_wifi():
    if not request.is_json:
        return jsonify({
            "status": "failed",
            "error": "Unsupported Media Type",
            "details": "Content-Type must be application/json"
        }), 415

    try:
        json_data = request.get_json()
        
        req = WifiRequest(**json_data)
        print(req.ssid,"|",req.password)
        res = configure_wifi_nmcli(req.ssid, req.password)

        stop_hotspot()

        res = connect_wifi_nmcli(req.ssid)
        if res.get('status') and res.get('status') == "failed":
            print(res)
            raise Unauthorized("Invalid wifi password")
        
        print(f"\n  connected to {req.ssid} >>>>>>>>>> \n")

        return jsonify({"status":"success", "message": f"Connected to Wi-Fi {req.ssid}"}), 200

    except ValidationError as e:
        start_hotspot()
        return jsonify({"status":"failed", "error": "Invalid data", "details": str(e)}), 400
    except HTTPException as e:
        start_hotspot()
        return jsonify({"status":"failed", "error": e.description}), e.code
    except subprocess.CalledProcessError as e:
        start_hotspot()
        return jsonify({"status":"failed", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        start_hotspot()
        return jsonify({"status":"failed", "error": "Server error", "details": str(e)}), 500
    

@main_bp.route("/scan-wifi", methods=["GET"])
def scan_wifi():
    try:
        res = scan_wifi_around()
        return jsonify(res), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        return jsonify({"success":"false", "error": "Server error", "details": str(e)}), 500

@main_bp.route("/get-connected-wifi", methods=["GET"])
def get_connected_wifi():
    try:
        res = get_connected_network()
        return jsonify(res), 200
    except subprocess.CalledProcessError as e:
        return jsonify({
            "success": "false",
            "error": "Failed to get connected WiFi",
            "details": e.output.decode("utf-8") if e.output else str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "success": "false",
            "error": "Server error",
            "details": str(e)
        }), 500


@main_bp.route("/start-hostspot", methods=["POST"])
def start_pi_hotspot():
    try:
        res = start_hotspot()
        if res['status'] != "success":
            return jsonify(res),500
        
        return jsonify(res),200

    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        return jsonify({"success":"false", "error": "Server error", "details": str(e)}), 500

@main_bp.route("/stop-hostspot", methods=["POST"])
def stop_pi_hotspot():
    try:
        res = stop_hotspot()
        if res['status'] != "success":
            return jsonify(res),404

        return jsonify(res),200

    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "Wi-Fi connection failed", "details": e.stderr}), 400
    except Exception as e:
        return jsonify({"success":"false", "error": "Server error", "details": str(e)}), 500


@main_bp.route('/start-ble',methods=["POST"])
def start_ble():
    try:
        res = start_ble_service()
        if res["status"]=="success" and "started" in res["message"]:
            return jsonify(res), 200
        return jsonify(res), 429
    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "sudo command failed", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"success":"false", "error": "somthing went wrong","details": str(e)}), 500

@main_bp.route('/stop-ble',methods=["POST"])
def stop_ble():
    try:
        res = stop_ble_service()
        if res["status"]=="success" and "stopped" in res["message"]:
            return jsonify(res), 200
        return jsonify(res), 429
    except subprocess.CalledProcessError as e:
        return jsonify({"success":"false", "error": "sudo command failed", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"success":"false", "error": "somthing went wrong", "details": str(e)}), 500
