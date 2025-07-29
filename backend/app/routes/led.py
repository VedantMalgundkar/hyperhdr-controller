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