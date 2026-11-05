"""The Reports & Trends page."""

from flask import Blueprint, render_template, request

from db import models
from utils.auth import login_required

reports_bp = Blueprint("reports", __name__)

TREND_VIEWS = ("daily", "weekly", "monthly")


@reports_bp.route("/reports")
@login_required
def index():
    granularity = request.args.get("view", "daily")
    if granularity not in TREND_VIEWS:
        granularity = "daily"
    return render_template("reports.html",
                           trend=models.get_sentiment_trend(granularity),
                           views=TREND_VIEWS,
                           products=models.get_product_performance_scores())
