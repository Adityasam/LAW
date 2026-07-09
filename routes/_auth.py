# routes/_auth.py
# Shared auth decorator for the JSON API blueprints.
from functools import wraps

from flask import jsonify, session


def login_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "firm_id" not in session:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function
