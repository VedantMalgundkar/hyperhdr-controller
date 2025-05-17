import os
import subprocess
from app import create_app
from flask import jsonify
from app.routes.main import main_bp
from app.routes.hyperhdr_install import hyperhdr_install_bp
from app.utils.hyperhdr_version_info import start_hotspot, is_paired
# from wifi_module import BLEServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # backend/
wifi_util_path = os.path.join(BASE_DIR, "wifi_module", "wifi_utilities.py")

app = create_app()
# ble_server = BLEServer()
ble_process = None

# app.register_blueprint(main_bp)
app.register_blueprint(hyperhdr_install_bp, url_prefix='/hyperhdr')


@app.route('/start-ble')
def start_ble():
    global ble_process
    if ble_process is None or ble_process.poll() is not None:
        ble_process = subprocess.Popen(["/usr/bin/python3", wifi_util_path])
        return jsonify({"status": "BLE started"}), 200
    return jsonify({"status": "BLE already running"}), 200

@app.route('/stop-ble')
def stop_ble():
    global ble_process
    if ble_process and ble_process.poll() is None:
        ble_process.terminate()
        ble_process = None
        return jsonify({"status": "BLE stopped"}), 200
    return jsonify({"status": "BLE not running"}), 200

@app.route('/')
def health_check():
    return jsonify(
        status="OK",
        message="Service is healthy"
    ), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False )