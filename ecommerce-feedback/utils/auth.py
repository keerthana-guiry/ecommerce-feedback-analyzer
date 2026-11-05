"""Login and permission checks shared by the routes."""

import hashlib
from functools import wraps

from flask import abort, g, redirect, session, url_for

from db import models


def _password_stamp(user):
    """A fingerprint of the user's password hash. Kept in the login cookie, so
    changing a password logs out everywhere that used the old one."""
    return hashlib.sha256(user["password_hash"].encode()).hexdigest()[:16]


def log_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["password_stamp"] = _password_stamp(user)


def login_required(view):
    """Check the account on every request, so deleted accounts and changed
    roles or passwords take effect straight away. Sets g.user for the page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = models.get_user_by_id(session["user_id"]) if "user_id" in session else None
        if not user or session.get("password_stamp") != _password_stamp(user):
            session.clear()
            return redirect(url_for("auth.login"))
        g.user = user
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def can_manage_review(review):
    """Admins can change any review. Analysts can change the ones they submitted."""
    return g.user["role"] == "admin" or review["submitted_by"] == g.user["id"]
