"""The Product Insights page, and adding products."""

import mysql.connector
from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import models
from utils.auth import admin_required, login_required
from utils.validation import product_name_error

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
@login_required
def index():
    return render_template("product_insights.html",
                           product_analytics=models.get_product_performance_scores(),
                           trending=models.get_trending_products())


@products_bp.route("/products", methods=["POST"])
@admin_required
def create():
    name = request.form.get("name", "").strip()
    error = product_name_error(name)
    if error:
        flash(error)
        return redirect(url_for("products.index"))

    try:
        models.add_product(name)
    except mysql.connector.IntegrityError:
        flash("That product already exists.")
    else:
        flash(f"Added the product {name}.")
    return redirect(url_for("products.index"))
