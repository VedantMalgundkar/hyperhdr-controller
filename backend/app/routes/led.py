import asyncio
from flask import Blueprint, jsonify, abort
from flask import request
from requests.exceptions import RequestException
from werkzeug.exceptions import HTTPException, Unauthorized, NotFound, BadRequest
from app.services.led_commands import (
    set_hyperhdr_brightness,
    get_hyperhdr_effects,
    apply_hyperhdr_effect,
    clear_hyperhdr_effect,
    get_current_brightness,
    check_input_signal,
    apply_hyperhdr_color,
    check_capture_card_signal,
    set_signal_detection,
    get_led_postion_data,
    get_led_stream,
)

led_bp = Blueprint("led", __name__)

@led_bp.route("/adjust-brightness", methods=["POST"])
def adjust_brightness():
    try:
        body = request.get_json()

        brightness = body.get('brightness')

        if brightness is None:
            raise NotFound(description="Missing 'brightness' in request body")
        
        brightness = int(brightness)

        if brightness > 100 or brightness < 0:
            raise BadRequest(description="Brightness should be between 0 to 100")

        res = set_hyperhdr_brightness(brightness)

        return jsonify({
            "status": "success",
            "data": res,
            "message": "Brightness adjusted successfully"
        }), 200

    except NotFound as e:
        return jsonify({"status": "failed", "error": str(e)}), 404

    except BadRequest as e:
        return jsonify({"status": "failed", "error": str(e)}), 400

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500

@led_bp.route("/get-brightness", methods=["GET"])
def get_brightness():
    try:
        res = get_current_brightness()
        
        return jsonify({
            "status": "success",
            "data": res,
            "message": "Fetched current brightness successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500

@led_bp.route("/get-effects", methods=["GET"])
def get_effects():
    try:
        res = get_hyperhdr_effects()
        
        return jsonify({
            "status": "success",
            "data": res,
            "message": "Fetched effect successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500

@led_bp.route("/apply-effect", methods=["POST"])
def apply_effect():
    try:
        body = request.get_json()
        effect = body.get('effect')
        
        if effect is None:
            raise NotFound(description="Missing 'effect' in request body")

        active_signal = check_input_signal()

        is_proto_running = 'proto' in active_signal.get("componentId","").lower()

        if is_proto_running:
            raise BadRequest("Disconnect Hyperion Grabber.")

        is_effect_running = active_signal.get("componentId","").lower() == "effect"

        if is_effect_running and active_signal["value"] == effect:
            return jsonify({
                "status": "success",
                "data": None,
                "message": "Effect already running"
            }), 200

        avl_effects = get_hyperhdr_effects()

        list_of_effects = [effect["name"] for effect in avl_effects]
        
        if effect not in list_of_effects:
            raise BadRequest(description="Unknown Effect")

        res = apply_hyperhdr_effect(effect)

        return jsonify({
            "status": "success",
            "data": res,
            "message": "effect applied successfully"
        }), 200

    except NotFound as e:
        return jsonify({"status": "failed", "error": str(e)}), 404

    except BadRequest as e:
        return jsonify({"status": "failed", "error": str(e)}), 400

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500

def is_valid_rgb(color):
    return (
        isinstance(color, list)
        and len(color) == 3
        and all(isinstance(c, int) and 0 <= c <= 255 for c in color)
    )

@led_bp.route("/apply-color", methods=["POST"])
def apply_color():
    try:
        body = request.get_json()

        color = body.get('color')
        
        if color is None:
            raise NotFound(description="Missing 'color' in request body")

        if not is_valid_rgb(color):
            raise BadRequest("Color must be 3 integers [0–255].")

        active_signal = check_input_signal()

        is_proto_running = 'proto' in active_signal.get("componentId","").lower()

        if is_proto_running:
            raise BadRequest("Disconnect Hyperion Grabber.")

        is_color_running = active_signal.get("componentId","").lower() == "color"
        
        if is_color_running and isinstance(active_signal["value"], dict) and active_signal["value"].get("RGB",[]) == color:
            return jsonify({
                "status": "success",
                "data": None,
                "message": "Color already applied"
            }), 200

        res = apply_hyperhdr_color(color)

        return jsonify({
            "status": "success",
            "data": res,
            "message": "color applied successfully"
        }), 200

    except NotFound as e:
        return jsonify({"status": "failed", "error": str(e)}), 404

    except BadRequest as e:
        return jsonify({"status": "failed", "error": str(e)}), 400

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500
    
@led_bp.route("/stop-effect", methods=["POST"])
def stop_effect():
    try:
        res = clear_hyperhdr_effect() 
        
        return jsonify({
            "status": "success",
            "data": res,
            "message": "Stopped effect successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500

@led_bp.route("/get-active-signal", methods=["GET"])
def get_active_signal():
    try:
        res = check_input_signal()
        
        return jsonify({
            "status": "success",
            "data": res,
            "message": "Fetched active input successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500    

@led_bp.route("/get-usb-signal", methods=["GET"])
def get_usb_signal():
    try:
        capture_card = check_capture_card_signal()

        return jsonify({
            "status": "success",
            "data": capture_card,
            "message": "Fetched usb input successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500    

@led_bp.route("/is-fallback", methods=["GET"])
async def is_fallback():
    try:
        led_position = get_led_postion_data()

        led_color = await get_led_stream()
        led_color = led_color.get("result",{}).get("leds",[])
        led_color = [led_color[i:i+3] for i in range(0, len(led_color), 3)]

        led_position = [{**each_position ,"color": led_color[index],"led_ind": index} for index,each_position in enumerate(led_position)]

        TOP_THRESHOLD = 0.05
        BOTTOM_THRESHOLD = 0.95

        top_leds = [
            led for led in led_position
            if led["vmin"] <= TOP_THRESHOLD and 0.05 < led["hmin"] < 0.95
        ]

        bottom_leds = [
            led for led in led_position
            if led["vmax"] >= BOTTOM_THRESHOLD and 0.05 < led["hmin"] < 0.95
        ]

        is_same_dir = True

        if top_leds[0]["color"] != bottom_leds[0]["color"]:
            is_same_dir = False

        loop_til = min(len(top_leds),len(bottom_leds))

        def colors_equal(c1, c2, tolerance=5):
            return all(abs(val1 - val2) <= tolerance for val1, val2 in zip(c1, c2))

        unmatched_count = 0
        for top_ind in range(loop_til):
            bottom_ind = top_ind
            if not is_same_dir:
                bottom_ind = len(bottom_leds) - top_ind - 1 
            
            top_color = top_leds[top_ind]["color"]
            bottom_color = bottom_leds[bottom_ind]["color"]

            if top_color != bottom_color and not colors_equal(top_color,bottom_color):
                # print(top_leds[top_ind]['led_ind'],"||",bottom_leds[bottom_ind]['led_ind'],top_color,"||",bottom_color)
                unmatched_count += 1          

        percenteage_matched = (loop_til - unmatched_count) / loop_til

        return jsonify({
            "status": "success",
            "data": percenteage_matched,
            "message": "fetched is fallback percentage."
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500    

@led_bp.route("/reconnect-signal", methods=["POST"])
def reconnect_signal():
    try:
        capture_card = check_capture_card_signal()

        res = None
        
        if not capture_card.get("active") and not capture_card.get("visible"):
            res = set_signal_detection(False)
            res = set_signal_detection(True)

        return jsonify({
            "status": "success",
            "data": res if res else {},
            "message": "ran reconnection successfully"
        }), 200

    except RequestException as e:
        return jsonify({"status": "failed", "error": f"API failed: {str(e)}"}), 500

    except Exception as e:
        return jsonify({"status": "failed", "error": f"Unexpected error: {str(e)}"}), 500    