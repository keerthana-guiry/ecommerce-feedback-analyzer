"""The Settings page."""

from flask import Blueprint, render_template

from utils.auth import login_required

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings")
@login_required
def index():
    return render_template("settings.html")
