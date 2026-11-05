"""Adding and analyzing reviews, browsing all reviews, and the CSV export."""

import csv
import io
from math import ceil

from flask import Blueprint, Response, flash, redirect, render_template, request, session, url_for

from db import models
from nlp.sentiment import analyze_sentiment
from utils.auth import login_required
from utils.export import safe_csv_cell

reviews_bp = Blueprint("reviews", __name__)

VALID_RATINGS = range(1, 6)
REVIEWS_PER_PAGE = 10
MAX_CUSTOMER_NAME_LENGTH = 100


@reviews_bp.route("/analyze", methods=["GET", "POST"])
@login_required
def analyze():
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        rating = request.form.get("rating", type=int)
        review_text = request.form.get("review_text", "").strip()
        customer_name = request.form.get("customer_name", "").strip()

        if not models.get_product_by_id(product_id):
            flash("Please choose a valid product.")
        elif rating not in VALID_RATINGS:
            flash("Please choose a rating from 1 to 5.")
        elif not review_text:
            flash("Please enter the review text.")
        elif len(customer_name) > MAX_CUSTOMER_NAME_LENGTH:
            flash(f"Customer name can be at most {MAX_CUSTOMER_NAME_LENGTH} characters.")
        else:
            review_id = models.add_review(
                product_id, rating, review_text, analyze_sentiment(review_text, rating),
                submitted_by=session["user_id"], customer_name=customer_name or None
            )
            return redirect(url_for("reviews.analyze", review=review_id))

    # Sentiment and aspects are the stored results. The word-level explanation
    # isn't stored, so it's recalculated for display from the original text.
    review = models.get_review(request.args.get("review", type=int))
    explanation = analyze_sentiment(review["review_text"], review["rating"]) if review else None
    return render_template("review_analysis.html", products=models.get_all_products(),
                           review=review, explanation=explanation)


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
        first=first
    )


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
