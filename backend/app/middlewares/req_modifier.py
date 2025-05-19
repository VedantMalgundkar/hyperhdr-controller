from functools import wraps
from flask import request, jsonify
import time
import os, pwd
import subprocess

def get_current_user():
    return pwd.getpwuid(os.getuid()).pw_name

def modify_request(add_data=None):
    """
    Decorator to modify the Flask request object.
    Args:
        add_data (dict): Key-value pairs to inject into request.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            request.custom_data = {
                "timestamp": time.time(),
                "user_agent": request.headers.get("User-Agent"),
                **(add_data or {}),
            }
            return f(*args, **kwargs)
        return wrapped
    return decorator