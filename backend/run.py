import threading
import asyncio
from app import create_app
from flask import jsonify
from app.routes.main import main_bp
from app.routes.hyperhdr_install import hyperhdr_install_bp
from app.utils.hyperhdr_version_info import start_hotspot, is_paired
from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
)

wifi_credentials = {}
# ble_stop_event = threading.Event()
ble_loop = asyncio.new_event_loop()

SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
CHAR_UUID = "abcdef01-1234-5678-1234-56789abcdef0"

app = create_app()

# app.register_blueprint(main_bp)
app.register_blueprint(hyperhdr_install_bp, url_prefix='/hyperhdr')

async def run_ble_server():
    server = BlessServer(name="BLE-WiFi-Config")

    def handle_write(value: bytes, options: dict):
        try:
            decoded = value.decode()
            if ":" in decoded:
                ssid, password = decoded.split(":", 1)
                wifi_credentials["ssid"] = ssid
                wifi_credentials["password"] = password
                print(f"✅ Received SSID: {ssid}, Password: {password}")
            else:
                print("❌ Malformed data received")
        except Exception as e:
            print("❌ Error handling write:", e)

    # Create the characteristic
    wifi_char = BlessGATTCharacteristic(
        uuid=CHAR_UUID,
        properties=GATTCharacteristicProperties.write,
        permissions=["write"],
        value=b''
    )
    wifi_char.write_callback = handle_write

    # Add service as a dictionary (since `BlessGATTService` is invalid)
    await server.add_service({
        "uuid": SERVICE_UUID,
        "characteristics": [wifi_char]
    })

    await server.start()
    print("✅ BLE server started.")
    await server.wait_for_stop()
    print("🛑 BLE server stopped.")

def ble_main():
    asyncio.set_event_loop(ble_loop)
    ble_loop.run_until_complete(run_ble_server())

@app.route('/start-ble')
def start_ble():
    if not ble_loop.is_running():
        threading.Thread(target=ble_main, daemon=True).start()
        return jsonify({"status": "BLE server starting..."})
    else:
        return jsonify({"status": "BLE already running"})

@app.route('/stop-ble')
def stop_ble():
    if ble_loop.is_running():
        ble_loop.call_soon_threadsafe(ble_loop.stop)
        return jsonify({"status": "BLE server stopping..."})
    else:
        return jsonify({"status": "BLE already stopped"})

@app.route('/wifi-creds')
def get_wifi_creds():
    return jsonify(wifi_credentials)


@app.route('/')
def health_check():
    return jsonify(
        status="OK",
        message="Service is healthy"
    ), 200

if __name__ == '__main__':
    # if not is_paired():
    #     start_hotspot()
    #     print("\n  started hotspot >>>>>>>>>> \n")

    app.run(host='0.0.0.0', port=5000, debug=False )