from app import create_app
from flask import jsonify
from app.routes.main import main_bp
from app.routes.hyperhdr_install import hyperhdr_install_bp
# backend/app/utils/hyperhdr_version_info.py
from app.utils.hyperhdr_version_info import start_hotspot, is_paired


app = create_app()

# app.register_blueprint(main_bp)
app.register_blueprint(hyperhdr_install_bp, url_prefix='/hyperhdr')

@app.route('/')
def health_check():
    return jsonify(
        status="OK",
        message="Service is healthy"
    ), 200

if __name__ == '__main__':
    if not is_paired():
        start_hotspot()
        print("\n  started hotspot >>>>>>>>>> \n")

    app.run(host='0.0.0.0', port=5000, debug=False )