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
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("customer_dashboard"))
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
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("customer_dashboard"))

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

@app.route("/customer", methods=["GET", "POST"])
@login_required
def customer_dashboard():
    products = db.get_all_products()

    if request.method == "POST":
        product_id = request.form.get("product_id")
        rating = int(request.form.get("rating", 3))
        review_text = request.form.get("review_text", "").strip()

        if review_text:
            result = analyze_sentiment(review_text, rating)
            db.add_feedback(
                session["user_id"], product_id, rating, review_text,
                result["sentiment"], result["score"], result["confidence"]
            )
            flash(f"Feedback submitted! Detected sentiment: {result['sentiment']}")
            return redirect(url_for("customer_dashboard"))

    history = db.get_feedback_for_user(session["user_id"])
    return render_template("customer_dashboard.html", products=products, history=history)


@app.route("/customer/edit/<int:feedback_id>", methods=["GET", "POST"])
@login_required
def edit_feedback(feedback_id):
    item = db.get_feedback_by_id(feedback_id)
    if not item or item["user_id"] != session["user_id"]:
        flash("Feedback not found.")
        return redirect(url_for("customer_dashboard"))

    if request.method == "POST":
        rating = int(request.form.get("rating", 3))
        review_text = request.form.get("review_text", "").strip()
        if review_text:
            result = analyze_sentiment(review_text, rating)
            db.update_feedback(
                feedback_id, rating, review_text,
                result["sentiment"], result["score"], result["confidence"]
            )
            flash(f"Feedback updated! New sentiment: {result['sentiment']}")
            return redirect(url_for("customer_dashboard"))

    products = db.get_all_products()
    return render_template("edit_feedback.html", item=item, products=products)


@app.route("/customer/delete/<int:feedback_id>", methods=["POST"])
@login_required
def delete_feedback(feedback_id):
    db.delete_feedback(feedback_id, session["user_id"])
    flash("Feedback deleted.")
    return redirect(url_for("customer_dashboard"))


# ---------- Admin routes ----------

@app.route("/admin")
@admin_required
def admin_dashboard():
    product_id = request.args.get("product_id", type=int)
    sentiment = request.args.get("sentiment")
    username = request.args.get("username")

    if product_id or sentiment or username:
        all_feedback = db.search_feedback(product_id, sentiment, username)
    else:
        all_feedback = db.get_all_feedback()

    sentiment_counts = db.get_sentiment_counts()
    product_analytics = db.get_product_analytics()
    products = db.get_all_products()

    return render_template(
        "admin_dashboard.html",
        feedback=all_feedback,
        sentiment_counts=sentiment_counts,
        product_analytics=product_analytics,
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
    writer.writerow(["Customer", "Product", "Rating", "Feedback", "Sentiment",
                      "Score", "Confidence", "Date"])
    for item in all_feedback:
        writer.writerow([
            item["username"], item["product_name"], item["rating"],
            item["review_text"], item["sentiment"], item["score"],
            item["confidence"], item["created_at"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=feedback_export.csv"}
    )


if __name__ == "__main__":
    app.run(debug=True)
