"""Adding, editing, uploading and browsing reviews, and the CSV export."""

import csv
import hashlib
import io
import os
from math import ceil

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)

from db import models
from nlp.sentiment import analyze_sentiment
from utils.auth import can_manage_review, login_required
from utils.csv_import import CsvFileError, parse_reviews_csv
from utils.export import safe_csv_cell
from utils.validation import review_error

reviews_bp = Blueprint("reviews", __name__)

REVIEWS_PER_PAGE = 10


def _read_review_form():
    """Returns the submitted review fields and an error message, or None if they're valid."""
    values = {
        "product_id": request.form.get("product_id", type=int),
        "rating": request.form.get("rating", type=int),
        "review_text": request.form.get("review_text", "").strip(),
        "customer_name": request.form.get("customer_name", "").strip(),
    }
    if not models.get_product_by_id(values["product_id"]):
        return values, "Please choose a valid product."
    return values, review_error(values["rating"], values["review_text"], values["customer_name"])


def _analyze_page(review=None, upload_errors=None):
    # Sentiment and aspects are the stored results. The word-level explanation
    # isn't stored, so it's recalculated for display from the original text.
    explanation = analyze_sentiment(review["review_text"], review["rating"]) if review else None
    return render_template("review_analysis.html", products=models.get_all_products(),
                           review=review, explanation=explanation, upload_errors=upload_errors)


def _manageable_review_or_abort(review_id):
    review = models.get_review(review_id)
    if not review:
        abort(404)
    if not can_manage_review(review):
        abort(403)
    return review


@reviews_bp.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    if request.method == "POST":
        values, error = _read_review_form()
        if error:
            flash(error)
        else:
            review_id = models.add_review(
                values["product_id"], values["rating"], values["review_text"],
                analyze_sentiment(values["review_text"], values["rating"]),
                submitted_by=g.user["id"], customer_name=values["customer_name"] or None
            )
            return redirect(url_for("reviews.analyze", review=review_id))

    return _analyze_page(review=models.get_review(request.args.get("review", type=int)))


@reviews_bp.route("/reviews/upload", methods=["POST"])
@login_required
def upload():
    """Add every review in a CSV file, or none of them if any row is invalid,
    so that fixing a file and uploading it again can't create duplicates."""
    file = request.files.get("file")
    if not file or not file.filename:
        return _analyze_page(upload_errors=["Please choose a CSV file."])
    if not file.filename.lower().endswith(".csv"):
        return _analyze_page(upload_errors=["Only .csv files can be uploaded."])

    raw = file.read()
    # Named by its contents, so the same file can't be imported twice by accident
    saved_path = os.path.join(current_app.config["UPLOAD_FOLDER"],
                              hashlib.sha256(raw).hexdigest() + ".csv")
    if os.path.exists(saved_path):
        return _analyze_page(upload_errors=["This exact file has already been uploaded."])

    product_ids = {product["name"].lower(): product["id"] for product in models.get_all_products()}
    try:
        rows, errors = parse_reviews_csv(raw, product_ids)
    except CsvFileError as error:
        return _analyze_page(upload_errors=[str(error)])
    if errors:
        return _analyze_page(upload_errors=errors)

    for row in rows:
        row["analysis"] = analyze_sentiment(row["review_text"], row["rating"])
    models.add_uploaded_reviews(rows, submitted_by=g.user["id"])

    with open(saved_path, "wb") as saved_file:
        saved_file.write(raw)

    flash(f"Added {len(rows)} reviews from {file.filename}.")
    return redirect(url_for("reviews.index"))


@reviews_bp.route("/reviews")
@login_required
def index():
    product_id = request.args.get("product_id", type=int)
    sentiment = request.args.get("sentiment") or None
    search = request.args.get("search", "").strip() or None
    rating = request.args.get("rating", type=int)
    sort = "oldest" if request.args.get("sort") == "oldest" else "newest"

    total = models.count_reviews(product_id, sentiment, search, rating)
    total_pages = max(ceil(total / REVIEWS_PER_PAGE), 1)
    page = min(max(request.args.get("page", 1, type=int), 1), total_pages)
    first = (page - 1) * REVIEWS_PER_PAGE

    return render_template(
        "all_reviews.html",
        reviews=models.search_reviews(product_id, sentiment, search, rating,
                                      oldest_first=sort == "oldest",
                                      limit=REVIEWS_PER_PAGE, offset=first),
        products=models.get_all_products(),
        filters={"product_id": product_id, "sentiment": sentiment, "search": search,
                 "rating": rating, "sort": sort},
        page=page,
        total_pages=total_pages,
        total=total,
        first=first,
        can_manage=can_manage_review
    )


@reviews_bp.route("/reviews/<int:review_id>/edit", methods=["GET", "POST"])
@login_required
def edit(review_id):
    review = _manageable_review_or_abort(review_id)
    values = review

    if request.method == "POST":
        values, error = _read_review_form()
        if error:
            flash(error)
        else:
            models.update_review(
                review_id, values["product_id"], values["rating"], values["review_text"],
                values["customer_name"] or None,
                analyze_sentiment(values["review_text"], values["rating"])
            )
            flash("The review was updated and analyzed again.")
            return redirect(url_for("reviews.analyze", review=review_id))

    return render_template("edit_review.html", review_id=review_id, values=values,
                           products=models.get_all_products())


@reviews_bp.route("/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def delete(review_id):
    _manageable_review_or_abort(review_id)
    models.delete_review(review_id)
    flash("The review was deleted.")
    # The page and filters come along in the query string, to return to the same list
    return redirect(url_for("reviews.index", **request.args.to_dict()))


@reviews_bp.route("/reviews/export")
@login_required
def export():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Customer", "Product", "Rating", "Review", "Sentiment", "Emotion",
                     "Score", "Confidence", "Spam Score", "Date"])
    for review in models.search_reviews():
        writer.writerow([safe_csv_cell(cell) for cell in (
            review["customer_name"] or "", review["product_name"], review["rating"],
            review["review_text"], review["sentiment"], review["emotion"] or "",
            review["score"], review["confidence"], review["spam_score"], review["review_date"]
        )])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=reviews_export.csv"}
    )
