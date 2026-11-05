"""
All MySQL queries for the app. Every value goes through a query parameter,
never directly into the SQL text, so user input can't change a query.
"""

from collections import Counter
from datetime import date, datetime, timedelta

from db.config import get_cursor
from nlp.sentiment import extract_keywords

SENTIMENTS = ("Positive", "Neutral", "Mixed", "Negative")

REVIEW_COLUMNS = """
    reviews.id, reviews.product_id, reviews.submitted_by, reviews.customer_name, reviews.rating,
    reviews.review_text, reviews.source, reviews.review_date,
    products.name AS product_name,
    sentiment_results.sentiment, sentiment_results.score,
    sentiment_results.confidence, sentiment_results.emotion,
    sentiment_results.spam_score, sentiment_results.model_name
"""

REVIEW_TABLES = """
    FROM reviews
    JOIN products ON reviews.product_id = products.id
    JOIN sentiment_results ON sentiment_results.review_id = reviews.id
"""


# ---------- Users ----------

def create_user(username, password_hash, role="analyst"):
    with get_cursor(commit=True) as cursor:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (username, password_hash, role)
        )
        return cursor.lastrowid


def get_user_by_username(username):
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def get_user_by_id(user_id):
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()


def get_all_users():
    """Every account, without the password hashes."""
    with get_cursor() as cursor:
        cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY username")
        return cursor.fetchall()


def update_username(user_id, username):
    with get_cursor(commit=True) as cursor:
        cursor.execute("UPDATE users SET username = %s WHERE id = %s", (username, user_id))


def update_password(user_id, password_hash):
    with get_cursor(commit=True) as cursor:
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


def update_default_days(user_id, days):
    with get_cursor(commit=True) as cursor:
        cursor.execute("UPDATE users SET default_days = %s WHERE id = %s", (days, user_id))


def delete_user(user_id):
    """Remove an account. Reviews it submitted are kept, with no submitter."""
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))


# ---------- Products ----------

def add_product(name):
    with get_cursor(commit=True) as cursor:
        cursor.execute("INSERT INTO products (name) VALUES (%s)", (name,))
        return cursor.lastrowid


def get_all_products():
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM products ORDER BY name")
        return cursor.fetchall()


def get_product_by_id(product_id):
    with get_cursor() as cursor:
        cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        return cursor.fetchone()


def get_product_analytics():
    """Per-product sentiment breakdown and average rating."""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT products.id, products.name,
                   COUNT(reviews.id) AS total,
                   SUM(sentiment_results.sentiment = 'Positive') AS positive,
                   SUM(sentiment_results.sentiment = 'Negative') AS negative,
                   SUM(sentiment_results.sentiment = 'Neutral') AS neutral,
                   SUM(sentiment_results.sentiment = 'Mixed') AS mixed,
                   AVG(reviews.rating) AS avg_rating
            FROM products
            LEFT JOIN reviews ON reviews.product_id = products.id
            LEFT JOIN sentiment_results ON sentiment_results.review_id = reviews.id
            GROUP BY products.id, products.name
            ORDER BY total DESC
        """)
        rows = cursor.fetchall()

    # MySQL returns SUM and AVG as Decimal, which doesn't convert cleanly to JSON
    return [{
        **row,
        "positive": int(row["positive"] or 0),
        "negative": int(row["negative"] or 0),
        "neutral": int(row["neutral"] or 0),
        "mixed": int(row["mixed"] or 0),
        "avg_rating": float(row["avg_rating"]) if row["avg_rating"] is not None else None,
    } for row in rows]


def get_product_performance_scores():
    """
    Compute a 0-100 Product Performance Score for each product, combining:
      - Average rating (normalized to 100)
      - Positive sentiment ratio
      - A small bonus for review volume (more data = more trustworthy)
    """
    scores = []
    for product in get_product_analytics():
        if product["total"] == 0:
            scores.append({**product, "performance_score": None})
            continue

        rating_component = product["avg_rating"] / 5 * 100
        sentiment_component = product["positive"] / product["total"] * 100
        volume_bonus = min(product["total"] / 20, 1) * 5  # up to +5 points for 20+ reviews

        raw_score = rating_component * 0.5 + sentiment_component * 0.45 + volume_bonus
        scores.append({**product, "performance_score": round(min(raw_score, 100), 1)})

    return sorted(scores, key=lambda p: p["performance_score"] or -1, reverse=True)


def get_trending_products(limit=5):
    """Returns the most reviewed, highest rated, and lowest rated products."""
    ranking_query = """
        SELECT products.name, AVG(reviews.rating) AS avg_rating, COUNT(reviews.id) AS total
        FROM products
        JOIN reviews ON reviews.product_id = products.id
        GROUP BY products.id, products.name
        ORDER BY {order}
        LIMIT %s
    """
    results = {}
    with get_cursor() as cursor:
        for name, order in (("most_reviewed", "total DESC"),
                            ("highest_rated", "avg_rating DESC"),
                            ("lowest_rated", "avg_rating ASC")):
            cursor.execute(ranking_query.format(order=order), (limit,))
            results[name] = cursor.fetchall()
    return results


# ---------- Reviews ----------

def _insert_analysis(cursor, review_id, analysis):
    cursor.execute("""
        INSERT INTO sentiment_results (review_id, sentiment, score, confidence,
                                       emotion, spam_score, model_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (review_id, analysis["sentiment"], analysis["score"], analysis["confidence"],
          analysis["emotion"], analysis["spam_score"], analysis["model_name"]))

    if analysis["aspects"]:
        cursor.executemany(
            "INSERT INTO aspect_results (review_id, aspect, sentiment) VALUES (%s, %s, %s)",
            [(review_id, aspect, sentiment) for aspect, sentiment in analysis["aspects"].items()]
        )


def _insert_review(cursor, product_id, rating, review_text, analysis, submitted_by,
                   customer_name, source, review_date):
    cursor.execute("""
        INSERT INTO reviews (product_id, submitted_by, customer_name, rating,
                             review_text, source, review_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (product_id, submitted_by, customer_name, rating, review_text, source,
          review_date or datetime.now()))
    review_id = cursor.lastrowid
    _insert_analysis(cursor, review_id, analysis)
    return review_id


def add_review(product_id, rating, review_text, analysis, submitted_by=None,
               customer_name=None, source="manual", review_date=None):
    """Save a review and its analysis results together. If any part fails,
    nothing is saved, so a review can never be left without its analysis."""
    with get_cursor(commit=True) as cursor:
        return _insert_review(cursor, product_id, rating, review_text, analysis, submitted_by,
                              customer_name, source, review_date)


def add_uploaded_reviews(rows, submitted_by):
    """Save all the rows of an uploaded file together, or none of them."""
    with get_cursor(commit=True) as cursor:
        for row in rows:
            _insert_review(cursor, row["product_id"], row["rating"], row["review_text"],
                           row["analysis"], submitted_by, row["customer_name"], "csv",
                           row["review_date"])


def update_review(review_id, product_id, rating, review_text, customer_name, analysis):
    """Save edits to a review and replace its old analysis with a new one."""
    with get_cursor(commit=True) as cursor:
        cursor.execute("""
            UPDATE reviews SET product_id = %s, rating = %s, review_text = %s, customer_name = %s
            WHERE id = %s
        """, (product_id, rating, review_text, customer_name, review_id))
        cursor.execute("DELETE FROM sentiment_results WHERE review_id = %s", (review_id,))
        cursor.execute("DELETE FROM aspect_results WHERE review_id = %s", (review_id,))
        _insert_analysis(cursor, review_id, analysis)


def delete_review(review_id):
    """Remove a review. Its analysis results are removed with it."""
    with get_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM reviews WHERE id = %s", (review_id,))


def get_review(review_id):
    """A review with its stored analysis and aspect results, or None."""
    with get_cursor() as cursor:
        cursor.execute(f"SELECT {REVIEW_COLUMNS} {REVIEW_TABLES} WHERE reviews.id = %s", (review_id,))
        review = cursor.fetchone()
        if review:
            cursor.execute(
                "SELECT aspect, sentiment FROM aspect_results WHERE review_id = %s ORDER BY aspect",
                (review_id,)
            )
            review["aspects"] = cursor.fetchall()
    return review


def get_recent_reviews(limit=5):
    with get_cursor() as cursor:
        cursor.execute(f"""
            SELECT {REVIEW_COLUMNS} {REVIEW_TABLES}
            ORDER BY reviews.review_date DESC, reviews.id DESC
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()


def _review_filters(product_id, sentiment, search, rating):
    conditions = []
    params = []
    if product_id:
        conditions.append("reviews.product_id = %s")
        params.append(product_id)
    if sentiment:
        conditions.append("sentiment_results.sentiment = %s")
        params.append(sentiment)
    if search:
        # Treat % and _ as ordinary characters, not LIKE wildcards
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("(reviews.review_text LIKE %s OR reviews.customer_name LIKE %s)")
        params.extend([f"%{escaped}%", f"%{escaped}%"])
    if rating:
        conditions.append("reviews.rating = %s")
        params.append(rating)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where, params


def count_reviews(product_id=None, sentiment=None, search=None, rating=None):
    where, params = _review_filters(product_id, sentiment, search, rating)
    with get_cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total {REVIEW_TABLES} {where}", params)
        return cursor.fetchone()["total"]


def search_reviews(product_id=None, sentiment=None, search=None, rating=None,
                   oldest_first=False, limit=None, offset=0):
    """Search and filter reviews. With a limit, returns one page of results."""
    where, params = _review_filters(product_id, sentiment, search, rating)
    direction = "ASC" if oldest_first else "DESC"
    query = f"""
        SELECT {REVIEW_COLUMNS} {REVIEW_TABLES} {where}
        ORDER BY reviews.review_date {direction}, reviews.id {direction}
    """
    if limit is not None:
        query += " LIMIT %s OFFSET %s"
        params = params + [limit, offset]

    with get_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def get_top_keywords(limit=10):
    """The sentiment words used most across all reviews."""
    with get_cursor() as cursor:
        cursor.execute("SELECT review_text FROM reviews")
        rows = cursor.fetchall()

    positive = Counter()
    negative = Counter()
    for row in rows:
        for word, polarity in extract_keywords(row["review_text"]):
            (positive if polarity == "positive" else negative)[word] += 1

    return {"top_positive": positive.most_common(limit), "top_negative": negative.most_common(limit)}


# ---------- Dashboard and trends ----------

def _empty_totals():
    return {"count": 0, "rating_sum": 0, "Positive": 0, "Negative": 0, "Neutral": 0, "Mixed": 0}


def _add_to_totals(totals, row):
    totals["count"] += row["count"]
    totals["rating_sum"] += int(row["rating_sum"])
    totals[row["sentiment"]] += row["count"]


def _avg_rating(totals):
    return totals["rating_sum"] / totals["count"] if totals["count"] else None


def _sentiment_rate(totals, sentiment):
    return totals[sentiment] / totals["count"] * 100 if totals["count"] else None


def _change(new, old):
    return round(new - old, 2) if new is not None and old is not None else None


def _daily_sentiment_rows(since):
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT DATE(reviews.review_date) AS day, sentiment_results.sentiment,
                   COUNT(*) AS count, SUM(reviews.rating) AS rating_sum
            FROM reviews
            JOIN sentiment_results ON sentiment_results.review_id = reviews.id
            WHERE reviews.review_date >= %s
            GROUP BY day, sentiment_results.sentiment
        """, (since,))
        return cursor.fetchall()


def get_dashboard_data(days=30):
    """Daily review counts for the last `days` days, plus KPI totals compared
    against the `days` days before that - powers the Dashboard page."""
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)

    labels = [start + timedelta(days=i) for i in range(days)]
    daily = {day: _empty_totals() for day in labels}
    current = _empty_totals()
    previous = _empty_totals()

    for row in _daily_sentiment_rows(previous_start):
        if row["day"] in daily:
            _add_to_totals(daily[row["day"]], row)
            _add_to_totals(current, row)
        elif row["day"] < start:
            _add_to_totals(previous, row)
        # Anything else is dated in the future, so it isn't counted

    days_data = [daily[day] for day in labels]
    avg_rating = _avg_rating(current)

    reviews_change = None
    if previous["count"]:
        reviews_change = round((current["count"] - previous["count"]) / previous["count"] * 100, 1)

    def rounded(values):
        return [round(v, 2) if v is not None else None for v in values]

    def rate_kpi(label, sentiment, higher_is_better):
        rate = _sentiment_rate(current, sentiment)
        return {
            "label": label,
            "value": f"{rate:.1f}%" if rate is not None else "—",
            "change": _change(rate, _sentiment_rate(previous, sentiment)),
            "unit": " pts",
            "higher_is_better": higher_is_better,
            "series": rounded(_sentiment_rate(d, sentiment) for d in days_data),
        }

    return {
        "days": days,
        "start": start,
        "end": today,
        "total": current["count"],
        "labels": [day.isoformat() for day in labels],
        "kpis": [
            {"label": "Total Reviews", "value": str(current["count"]),
             "change": reviews_change, "unit": "%", "higher_is_better": True,
             "series": [d["count"] for d in days_data]},
            rate_kpi("Positive", "Positive", True),
            rate_kpi("Neutral", "Neutral", None),
            rate_kpi("Negative", "Negative", False),
            {"label": "Average Rating",
             "value": f"{avg_rating:.2f}" if avg_rating is not None else "—",
             "change": _change(avg_rating, _avg_rating(previous)), "unit": "★",
             "higher_is_better": True,
             "series": rounded(_avg_rating(d) for d in days_data)},
        ],
        "distribution": {name: current[name] for name in SENTIMENTS},
    }


def get_sentiment_trend(granularity="daily"):
    """Sentiment counts, average rating and positive rate grouped by day,
    week or month - powers the Reports & Trends page. Periods with no
    reviews are kept, with empty values, so the charts show real gaps."""
    today = datetime.now().date()

    if granularity == "weekly":
        this_week = today - timedelta(days=today.weekday())
        starts = [this_week - timedelta(weeks=i) for i in range(11, -1, -1)]
        bucket_of = lambda day: day - timedelta(days=day.weekday())
        label_of = lambda start: "Week of " + start.strftime("%b %d")
    elif granularity == "monthly":
        starts = []
        year, month = today.year, today.month
        for _ in range(12):
            starts.insert(0, date(year, month, 1))
            year, month = (year - 1, 12) if month == 1 else (year, month - 1)
        bucket_of = lambda day: day.replace(day=1)
        label_of = lambda start: start.strftime("%b %Y")
    else:
        starts = [today - timedelta(days=i) for i in range(29, -1, -1)]
        bucket_of = lambda day: day
        label_of = lambda start: start.strftime("%b %d")

    buckets = {start: _empty_totals() for start in starts}
    for row in _daily_sentiment_rows(starts[0]):
        totals = buckets.get(bucket_of(row["day"]))
        if totals:
            _add_to_totals(totals, row)

    periods = [buckets[start] for start in starts]
    positive_rates = [_sentiment_rate(p, "Positive") for p in periods]
    avg_ratings = [_avg_rating(p) for p in periods]

    return {
        "granularity": granularity,
        "labels": [label_of(start) for start in starts],
        "total": sum(p["count"] for p in periods),
        "sentiment_series": {name: [p[name] for p in periods] for name in SENTIMENTS},
        "positive_rate": [round(v, 1) if v is not None else None for v in positive_rates],
        "avg_rating": [round(v, 2) if v is not None else None for v in avg_ratings],
    }
