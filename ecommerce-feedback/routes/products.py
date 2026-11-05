"""The Product Insights page."""

from flask import Blueprint, render_template

from db import models
from utils.auth import login_required

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
@login_required
def index():
    return render_template("product_insights.html",
                           product_analytics=models.get_product_performance_scores(),
                           trending=models.get_trending_products())
