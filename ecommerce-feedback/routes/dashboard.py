"""The main Dashboard page."""

from flask import Blueprint, render_template, request

from db import models
from utils.auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)

PERIOD_OPTIONS = (7, 30, 90)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    days = request.args.get("days", 30, type=int)
    if days not in PERIOD_OPTIONS:
        days = 30
    return render_template(
        "dashboard.html",
        dashboard=models.get_dashboard_data(days),
        period_options=PERIOD_OPTIONS,
        products=models.get_product_performance_scores()[:5],
        keywords=models.get_top_keywords(limit=5),
        recent_reviews=models.get_recent_reviews()
    )
