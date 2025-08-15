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
    check_top_bottom_led_for_fallback,
    transform_flat_led_colors_for_each_led,
    add_color_to_led_position_data,
    get_leds_by_direction,
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
async def apply_effect():
    try:
        body = request.get_json()
        effect = body.get('effect')
        
        if effect is None:
            raise NotFound(description="Missing 'effect' in request body")

        active_signal = await check_input_signal()

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
async def apply_color():
    try:
        body = request.get_json()

        color = body.get('color')
        
        if color is None:
            raise NotFound(description="Missing 'color' in request body")

        if not is_valid_rgb(color):
            raise BadRequest("Color must be 3 integers [0–255].")

        active_signal = await check_input_signal()

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
async def get_active_signal():
    try:
        res = await check_input_signal()
        
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

        led_color = transform_flat_led_colors_for_each_led(led_color)

        led_position = add_color_to_led_position_data(led_position, led_color)

        TOP_THRESHOLD = 0.05
        BOTTOM_THRESHOLD = 0.95

        result = get_leds_by_direction(led_position,TOP_THRESHOLD=TOP_THRESHOLD, BOTTOM_THRESHOLD = BOTTOM_THRESHOLD)

        is_it_fallback = check_top_bottom_led_for_fallback(result["top"], result["bottom"])

        return jsonify({
            "status": "success",
            "data": { "is_fallback": is_it_fallback },
            "message": "fetched fallback status successfully."
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