import os
import subprocess
from app import create_app
from flask import jsonify
from app.routes.main import main_bp
from app.routes.hyperhdr_install import hyperhdr_install_bp

app = create_app()

# app.register_blueprint(main_bp)
app.register_blueprint(hyperhdr_install_bp, url_prefix="/hyperhdr")


@app.route("/")
def health_check():
    return jsonify(status="OK", message="Service is healthy"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
