import os
import secrets
from math import ceil

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

import database as db
from sentiment import analyze_sentiment

app = Flask(__name__)
# Without SECRET_KEY set, a random key means everyone is logged out on restart
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
CSRFProtect(app)

db.init_db()


# ---------- Auth helpers ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


# ---------- Auth routes ----------

@app.route("/", methods=["GET"])
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_sentiment"))
        return redirect(url_for("leave_feedback"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("admin_sentiment"))
            return redirect(url_for("leave_feedback"))

        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.")
        elif db.get_user_by_username(username):
            flash("Username already taken.")
        else:
            db.create_user(username, generate_password_hash(password), role="customer")
            flash("Account created! Please log in.")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Customer routes ----------

VALID_RATINGS = range(1, 6)


@app.route("/customer/feedback", methods=["GET", "POST"])
@login_required
def leave_feedback():
    products = db.get_all_products()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        rating = request.form.get("rating", type=int)
        review_text = request.form.get("review_text", "").strip()

        if not db.get_product_by_id(product_id):
            flash("Please choose a valid product.")
        elif rating not in VALID_RATINGS:
            flash("Please choose a rating from 1 to 5.")
        elif review_text:
            result = analyze_sentiment(review_text, rating)
            db.add_feedback(
                session["user_id"], product_id, rating, review_text,
                result["sentiment"], result["score"], result["confidence"],
                result["emotion"], result["spam_score"]
            )
            flash(f"Feedback submitted! Detected sentiment: {result['sentiment']}"
                  + (f" {result['emotion']}" if result['emotion'] else ""))
            if result["likely_spam"]:
                flash("Note: this review was flagged for review by our system (unusual pattern detected).")
            return redirect(url_for("feedback_history"))

    return render_template("leave_feedback.html", products=products)


@app.route("/customer/history")
@login_required
def feedback_history():
    history = db.get_feedback_for_user(session["user_id"])
    return render_template("feedback_history.html", history=history)


@app.route("/customer/edit/<int:feedback_id>", methods=["GET", "POST"])
@login_required
def edit_feedback(feedback_id):
    item = db.get_feedback_by_id(feedback_id)
    if not item or item["user_id"] != session["user_id"]:
        flash("Feedback not found.")
        return redirect(url_for("feedback_history"))

    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        review_text = request.form.get("review_text", "").strip()
        if rating not in VALID_RATINGS:
            flash("Please choose a rating from 1 to 5.")
        elif review_text:
            result = analyze_sentiment(review_text, rating)
            db.update_feedback(
                feedback_id, rating, review_text,
                result["sentiment"], result["score"], result["confidence"],
                result["emotion"], result["spam_score"]
            )
            flash(f"Feedback updated! New sentiment: {result['sentiment']}")
            return redirect(url_for("feedback_history"))

    products = db.get_all_products()
    return render_template("edit_feedback.html", item=item, products=products)


@app.route("/customer/delete/<int:feedback_id>", methods=["POST"])
@login_required
def delete_feedback(feedback_id):
    db.delete_feedback(feedback_id, session["user_id"])
    flash("Feedback deleted.")
    return redirect(url_for("feedback_history"))


@app.route("/feedback/vote/<int:feedback_id>/<vote>", methods=["POST"])
@login_required
def cast_vote(feedback_id, vote):
    if vote not in ("helpful", "not_helpful") or not db.get_feedback_by_id(feedback_id):
        return redirect(request.referrer or url_for("admin_feedback"))
    db.vote_feedback(feedback_id, session["user_id"], vote)
    return redirect(request.referrer or url_for("admin_feedback"))


# ---------- Admin routes ----------

PERIOD_OPTIONS = (7, 30, 90)
TREND_VIEWS = ("daily", "weekly", "monthly")
FEEDBACK_PER_PAGE = 10


@app.route("/admin/sentiment")
@admin_required
def admin_sentiment():
    days = request.args.get("days", 30, type=int)
    if days not in PERIOD_OPTIONS:
        days = 30
    return render_template(
        "admin_sentiment.html",
        dashboard=db.get_dashboard_data(days),
        period_options=PERIOD_OPTIONS,
        products=db.get_product_performance_scores()[:5],
        keywords=db.get_top_keywords(limit=5),
        recent_reviews=db.get_recent_feedback()
    )


@app.route("/admin/analyze", methods=["GET", "POST"])
@admin_required
def admin_analyze():
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        rating = request.form.get("rating", type=int)
        review_text = request.form.get("review_text", "").strip()

        if not db.get_product_by_id(product_id):
            flash("Please choose a valid product.")
        elif rating not in VALID_RATINGS:
            flash("Please choose a rating from 1 to 5.")
        elif not review_text:
            flash("Please enter the review text.")
        else:
            result = analyze_sentiment(review_text, rating)
            review_id = db.add_feedback(
                session["user_id"], product_id, rating, review_text,
                result["sentiment"], result["score"], result["confidence"],
                result["emotion"], result["spam_score"]
            )
            return redirect(url_for("admin_analyze", review=review_id))

    # Show the analysis of the review just saved, recalculated from its stored text
    review = db.get_feedback_by_id(request.args.get("review", type=int))
    result = analyze_sentiment(review["review_text"], review["rating"]) if review else None
    return render_template("admin_analyze.html", products=db.get_all_products(),
                           review=review, result=result)


@app.route("/admin/products")
@admin_required
def admin_products():
    product_analytics = db.get_product_performance_scores()
    trending = db.get_trending_products()
    return render_template("admin_products.html", product_analytics=product_analytics,
                            trending=trending)


@app.route("/admin/reports")
@admin_required
def admin_reports():
    granularity = request.args.get("view", "daily")
    if granularity not in TREND_VIEWS:
        granularity = "daily"
    return render_template(
        "admin_reports.html",
        trend=db.get_sentiment_trend(granularity),
        views=TREND_VIEWS,
        products=db.get_product_performance_scores()
    )


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    product_id = request.args.get("product_id", type=int)
    sentiment = request.args.get("sentiment") or None
    search = request.args.get("search", "").strip() or None
    rating = request.args.get("rating", type=int)
    sort = "oldest" if request.args.get("sort") == "oldest" else "newest"

    all_feedback = db.search_feedback(product_id, sentiment, search, rating,
                                      oldest_first=sort == "oldest")
    products = db.get_all_products()

    total = len(all_feedback)
    total_pages = max(ceil(total / FEEDBACK_PER_PAGE), 1)
    page = min(max(request.args.get("page", 1, type=int), 1), total_pages)
    first = (page - 1) * FEEDBACK_PER_PAGE

    return render_template(
        "admin_feedback.html",
        feedback=all_feedback[first:first + FEEDBACK_PER_PAGE],
        products=products,
        filters={"product_id": product_id, "sentiment": sentiment, "search": search,
                 "rating": rating, "sort": sort},
        page=page,
        total_pages=total_pages,
        total=total,
        first=first
    )


@app.route("/admin/export")
@admin_required
def export_csv():
    import csv
    import io
    from flask import Response

    all_feedback = db.get_all_feedback()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Customer", "Product", "Rating", "Feedback", "Sentiment", "Emotion",
                      "Score", "Confidence", "Spam Score", "Helpful Votes", "Date"])
    for item in all_feedback:
        writer.writerow([
            item["username"], item["product_name"], item["rating"],
            item["review_text"], item["sentiment"], item["emotion"] or "",
            item["score"], item["confidence"], item["spam_score"] or 0,
            item["helpful_votes"] or 0, item["created_at"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback_export.csv"}
    )


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
