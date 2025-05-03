from flask import Blueprint, jsonify
import subprocess
from flask import request
from app.utils.req_modifier import modify_request, get_current_user
from app.utils.hyperhdr_version_info import start_hyperhdr_service,stop_hyperhdr_service,status_hyperhdr_service,get_hyperhdr_version,fetch_github_versions


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