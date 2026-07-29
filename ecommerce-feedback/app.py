from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

import database as db
from sentiment import analyze_sentiment

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"

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

@app.route("/customer/feedback", methods=["GET", "POST"])
@login_required
def leave_feedback():
    products = db.get_all_products()

    if request.method == "POST":
        product_id = request.form.get("product_id")
        rating = int(request.form.get("rating", 3))
        review_text = request.form.get("review_text", "").strip()

        if review_text:
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
        rating = int(request.form.get("rating", 3))
        review_text = request.form.get("review_text", "").strip()
        if review_text:
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
    if vote not in ("helpful", "not_helpful"):
        return redirect(request.referrer or url_for("admin_feedback"))
    db.vote_feedback(feedback_id, session["user_id"], vote)
    return redirect(request.referrer or url_for("admin_feedback"))


# ---------- Admin routes ----------

@app.route("/admin/sentiment")
@admin_required
def admin_sentiment():
    sentiment_counts = db.get_sentiment_counts()
    return render_template("admin_sentiment.html", sentiment_counts=sentiment_counts)


@app.route("/admin/products")
@admin_required
def admin_products():
    product_analytics = db.get_product_performance_scores()
    trending = db.get_trending_products()
    return render_template("admin_products.html", product_analytics=product_analytics,
                            trending=trending)


@app.route("/admin/insights")
@admin_required
def admin_insights():
    keywords = db.get_top_keywords()
    return render_template("admin_insights.html", keywords=keywords)


@app.route("/admin/feedback")
@admin_required
def admin_feedback():
    product_id = request.args.get("product_id", type=int)
    sentiment = request.args.get("sentiment")
    username = request.args.get("username")

    if product_id or sentiment or username:
        all_feedback = db.search_feedback(product_id, sentiment, username)
    else:
        all_feedback = db.get_all_feedback()

    products = db.get_all_products()

    return render_template(
        "admin_feedback.html",
        feedback=all_feedback,
        products=products,
        filters={"product_id": product_id, "sentiment": sentiment, "username": username}
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
    app.run(debug=True)
