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
)

led_bp = Blueprint("led", __name__)

currently_running_effect = ""

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

@led_bp.route("/get-current-effect", methods=["GET"])
def get_current_effect():
    print(currently_running_effect)
    return jsonify({
        "status": "success",
        "data": {
            "current_effect": None if currently_running_effect == "" else currently_running_effect 
        },
        "message": "Fetched current effect successfully"
    }), 200

@led_bp.route("/apply-effect", methods=["POST"])
def apply_effect():
    global currently_running_effect
    try:
        body = request.get_json()

        effect = body.get('effect')
        
        if effect is None:
            raise NotFound(description="Missing 'effect' in request body")
        
        if currently_running_effect == effect:
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

        currently_running_effect = effect

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
    
@led_bp.route("/stop-effect", methods=["POST"])
def stop_effect():
    try:
        global currently_running_effect

        res = clear_hyperhdr_effect()

        currently_running_effect = ""
        
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




    