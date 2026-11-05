"""The Settings page: your own profile, and account management for admins."""

import mysql.connector
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import models
from nlp.sentiment import CURRENT_MODELS, analyze_sentiment
from routes.dashboard import PERIOD_OPTIONS
from utils.auth import admin_required, log_in, login_required
from utils.validation import password_error, username_error

settings_bp = Blueprint("settings", __name__)

REANALYZE_BATCH_SIZE = 200


def _back_to_settings():
    return redirect(url_for("settings.index"))


@settings_bp.route("/settings")
@login_required
def index():
    is_admin = g.user["role"] == "admin"
    model_counts = models.count_reviews_by_model() if is_admin else None
    return render_template(
        "settings.html",
        users=models.get_all_users() if is_admin else None,
        model_counts=model_counts,
        outdated_reviews=sum(row["total"] for row in model_counts or []
                             if row["model_name"] not in CURRENT_MODELS),
        period_options=PERIOD_OPTIONS
    )


@settings_bp.route("/settings/profile", methods=["POST"])
@login_required
def update_profile():
    username = request.form.get("username", "").strip()
    error = username_error(username)
    if error:
        flash(error)
        return _back_to_settings()

    try:
        models.update_username(g.user["id"], username)
    except mysql.connector.IntegrityError:
        flash("That username is already taken.")
    else:
        flash("Your username was updated.")
    return _back_to_settings()


@settings_bp.route("/settings/password", methods=["POST"])
@login_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")

    if not check_password_hash(g.user["password_hash"], current):
        flash("Your current password wasn't correct.")
    elif new != request.form.get("confirm_password", ""):
        flash("The new passwords didn't match.")
    elif password_error(new):
        flash(password_error(new))
    else:
        models.update_password(g.user["id"], generate_password_hash(new))
        # Stay logged in here. Anywhere else using the old password is logged out.
        log_in(models.get_user_by_id(g.user["id"]))
        flash("Your password was changed.")
    return _back_to_settings()


@settings_bp.route("/settings/preferences", methods=["POST"])
@login_required
def update_preferences():
    days = request.form.get("default_days", type=int)
    if days in PERIOD_OPTIONS:
        models.update_default_days(g.user["id"], days)
        flash("Your preferences were saved.")
    else:
        flash("Please choose one of the listed time periods.")
    return _back_to_settings()


# ---------- Re-analyzing older reviews (admins only) ----------

@settings_bp.route("/settings/reanalyze", methods=["POST"])
@admin_required
def reanalyze():
    """Analyze reviews again if an older engine produced their results. Each batch
    saves separately, so if this stops early, running it again carries on."""
    updated = 0
    while batch := models.get_reviews_on_old_models(CURRENT_MODELS, REANALYZE_BATCH_SIZE):
        models.save_new_analyses([(review["id"], analyze_sentiment(review["review_text"], review["rating"]))
                                  for review in batch])
        updated += len(batch)

    flash(f"Analyzed {updated} reviews again." if updated else "All reviews are already up to date.")
    return _back_to_settings()


# ---------- Managing accounts (admins only) ----------

@settings_bp.route("/settings/users", methods=["POST"])
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role")

    error = username_error(username) or password_error(password)
    if role not in ("admin", "analyst"):
        error = "Please choose a role."
    if error:
        flash(error)
        return _back_to_settings()

    try:
        models.create_user(username, generate_password_hash(password), role=role)
    except mysql.connector.IntegrityError:
        flash("That username is already taken.")
    else:
        flash(f"Created the account {username}.")
    return _back_to_settings()


@settings_bp.route("/settings/users/<int:user_id>/password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id):
    user = models.get_user_by_id(user_id)
    if not user:
        abort(404)
    if user_id == g.user["id"]:
        return _back_to_settings()  # Your own password needs your current one

    if request.method == "POST":
        password = request.form.get("password", "")
        if password_error(password):
            flash(password_error(password))
        else:
            models.update_password(user_id, generate_password_hash(password))
            flash(f"Reset the password for {user['username']}.")
            return _back_to_settings()
    return render_template("reset_password.html", account=user)


@settings_bp.route("/settings/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    # Admins can't remove themselves, so there's always at least one admin left
    if user_id == g.user["id"]:
        flash("You can't delete your own account.")
    else:
        models.delete_user(user_id)
        flash("The account was deleted. Its reviews were kept.")
    return _back_to_settings()
