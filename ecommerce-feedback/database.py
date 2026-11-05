"""
Database setup for the E-Commerce Feedback Analyzer.
Uses SQLite - no server setup needed, just a local file.
"""

import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash

DB_NAME = os.environ.get(
    "FEEDBACK_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback.db")
)

SENTIMENTS = ("Positive", "Neutral", "Mixed", "Negative")

SAMPLE_PRODUCTS = [
    "Wireless Bluetooth Earbuds",
    "Smart Fitness Watch",
    "Stainless Steel Water Bottle",
    "Ergonomic Office Chair",
    "Portable Power Bank 20000mAh",
    "Laptop Backpack",
]


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('customer', 'admin'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            review_text TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            score REAL NOT NULL,
            confidence REAL NOT NULL,
            emotion TEXT,
            spam_score INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            not_helpful_votes INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vote TEXT NOT NULL CHECK(vote IN ('helpful', 'not_helpful')),
            UNIQUE(feedback_id, user_id),
            FOREIGN KEY (feedback_id) REFERENCES feedback(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Seed products if empty
    cur.execute("SELECT COUNT(*) as c FROM products")
    if cur.fetchone()["c"] == 0:
        for name in SAMPLE_PRODUCTS:
            cur.execute("INSERT INTO products (name) VALUES (?)", (name,))

    # Seed a default admin account if no admin exists
    cur.execute("SELECT COUNT(*) as c FROM users WHERE role = 'admin'")
    if cur.fetchone()["c"] == 0:
        admin_password = os.environ.get("ADMIN_PASSWORD")
        if not admin_password:
            admin_password = secrets.token_urlsafe(12)
            print(f"Created admin account. Username: admin, password: {admin_password}")
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash(admin_password), "admin")
        )

    conn.commit()
    conn.close()


def get_all_products():
    conn = get_connection()
    products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return products


def get_product_by_id(product_id):
    conn = get_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return product


def create_user(username, password_hash, role="customer"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role)
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return user


def add_feedback(user_id, product_id, rating, review_text, sentiment, score,
                  confidence, emotion=None, spam_score=0, created_at=None):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO feedback (user_id, product_id, rating, review_text,
                               sentiment, score, confidence, emotion,
                               spam_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, product_id, rating, review_text, sentiment, score,
          confidence, emotion, spam_score,
          created_at or datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_feedback_for_user(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT feedback.*, products.name as product_name
        FROM feedback
        JOIN products ON feedback.product_id = products.id
        WHERE feedback.user_id = ?
        ORDER BY feedback.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows


def get_all_feedback():
    conn = get_connection()
    rows = conn.execute("""
        SELECT feedback.*, products.name as product_name, users.username
        FROM feedback
        JOIN products ON feedback.product_id = products.id
        JOIN users ON feedback.user_id = users.id
        ORDER BY feedback.created_at DESC
    """).fetchall()
    conn.close()
    return rows


def _empty_totals():
    return {"count": 0, "rating_sum": 0, "flagged": 0,
            "Positive": 0, "Negative": 0, "Neutral": 0, "Mixed": 0}


def _avg_rating(totals):
    return totals["rating_sum"] / totals["count"] if totals["count"] else None


def _sentiment_rate(totals, sentiment):
    return totals[sentiment] / totals["count"] * 100 if totals["count"] else None


def _change(new, old):
    return round(new - old, 2) if new is not None and old is not None else None


def get_dashboard_data(days=30):
    """Daily review counts for the last `days` days, plus KPI totals compared
    against the `days` days before that - powers the admin overview page."""
    today = datetime.now().date()
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)

    conn = get_connection()
    rows = conn.execute("""
        SELECT substr(created_at, 1, 10) as day, sentiment,
               COUNT(*) as count,
               SUM(rating) as rating_sum,
               SUM(CASE WHEN spam_score >= 50 THEN 1 ELSE 0 END) as flagged
        FROM feedback
        WHERE substr(created_at, 1, 10) >= ?
        GROUP BY day, sentiment
    """, (previous_start.isoformat(),)).fetchall()
    conn.close()

    labels = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    daily = {day: _empty_totals() for day in labels}
    current = _empty_totals()
    previous = _empty_totals()

    for row in rows:
        if row["day"] in daily:
            targets = [daily[row["day"]], current]
        elif row["day"] < start.isoformat():
            targets = [previous]
        else:
            continue  # dated in the future
        for totals in targets:
            totals["count"] += row["count"]
            totals["rating_sum"] += row["rating_sum"]
            totals["flagged"] += row["flagged"]
            totals[row["sentiment"]] += row["count"]

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
        "labels": labels,
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

    conn = get_connection()
    rows = conn.execute("""
        SELECT substr(created_at, 1, 10) as day, sentiment,
               COUNT(*) as count, SUM(rating) as rating_sum
        FROM feedback
        WHERE substr(created_at, 1, 10) >= ?
        GROUP BY day, sentiment
    """, (starts[0].isoformat(),)).fetchall()
    conn.close()

    buckets = {start: _empty_totals() for start in starts}
    for row in rows:
        totals = buckets.get(bucket_of(date.fromisoformat(row["day"])))
        if totals:
            totals["count"] += row["count"]
            totals["rating_sum"] += row["rating_sum"]
            totals[row["sentiment"]] += row["count"]

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


def get_product_analytics():
    """Per-product sentiment breakdown and average rating - powers the
    'which products are causing problems' view for admins."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT products.id, products.name,
               COUNT(feedback.id) as total,
               SUM(CASE WHEN sentiment = 'Positive' THEN 1 ELSE 0 END) as positive,
               SUM(CASE WHEN sentiment = 'Negative' THEN 1 ELSE 0 END) as negative,
               SUM(CASE WHEN sentiment = 'Neutral' THEN 1 ELSE 0 END) as neutral,
               SUM(CASE WHEN sentiment = 'Mixed' THEN 1 ELSE 0 END) as mixed,
               AVG(rating) as avg_rating
        FROM products
        LEFT JOIN feedback ON feedback.product_id = products.id
        GROUP BY products.id
        ORDER BY total DESC
    """).fetchall()
    conn.close()
    return rows


def get_feedback_by_id(feedback_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM feedback WHERE id = ?", (feedback_id,)).fetchone()
    conn.close()
    return row


def update_feedback(feedback_id, rating, review_text, sentiment, score,
                     confidence, emotion=None, spam_score=0):
    conn = get_connection()
    conn.execute("""
        UPDATE feedback
        SET rating = ?, review_text = ?, sentiment = ?, score = ?,
            confidence = ?, emotion = ?, spam_score = ?
        WHERE id = ?
    """, (rating, review_text, sentiment, score, confidence, emotion,
          spam_score, feedback_id))
    conn.commit()
    conn.close()


def delete_feedback(feedback_id, user_id):
    """Only deletes if the feedback belongs to that user (customers can't delete others')."""
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM feedback WHERE id = ? AND user_id = ?", (feedback_id, user_id)
    )
    if cur.rowcount:
        conn.execute("DELETE FROM feedback_votes WHERE feedback_id = ?", (feedback_id,))
    conn.commit()
    conn.close()


def get_recent_feedback(limit=5):
    conn = get_connection()
    rows = conn.execute("""
        SELECT feedback.*, products.name as product_name, users.username
        FROM feedback
        JOIN products ON feedback.product_id = products.id
        JOIN users ON feedback.user_id = users.id
        ORDER BY feedback.created_at DESC, feedback.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def search_feedback(product_id=None, sentiment=None, search=None, rating=None, oldest_first=False):
    """Search and filter across all feedback, for the All Reviews page."""
    conn = get_connection()
    query = """
        SELECT feedback.*, products.name as product_name, users.username
        FROM feedback
        JOIN products ON feedback.product_id = products.id
        JOIN users ON feedback.user_id = users.id
        WHERE 1=1
    """
    params = []

    if product_id:
        query += " AND feedback.product_id = ?"
        params.append(product_id)
    if sentiment:
        query += " AND feedback.sentiment = ?"
        params.append(sentiment)
    if search:
        query += " AND (feedback.review_text LIKE ? OR users.username LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if rating:
        query += " AND feedback.rating = ?"
        params.append(rating)

    query += " ORDER BY feedback.created_at " + ("ASC" if oldest_first else "DESC")

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def vote_feedback(feedback_id, user_id, vote):
    """Cast or change a helpful/not_helpful vote. One vote per user per review."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM feedback_votes WHERE feedback_id = ? AND user_id = ?",
        (feedback_id, user_id)
    ).fetchone()

    if existing:
        if existing["vote"] == vote:
            conn.close()
            return  # already voted this way, no-op
        conn.execute(
            "UPDATE feedback_votes SET vote = ? WHERE feedback_id = ? AND user_id = ?",
            (vote, feedback_id, user_id)
        )
        # adjust counts: remove old vote, add new
        old_col = "helpful_votes" if existing["vote"] == "helpful" else "not_helpful_votes"
        new_col = "helpful_votes" if vote == "helpful" else "not_helpful_votes"
        conn.execute(f"UPDATE feedback SET {old_col} = {old_col} - 1 WHERE id = ?", (feedback_id,))
        conn.execute(f"UPDATE feedback SET {new_col} = {new_col} + 1 WHERE id = ?", (feedback_id,))
    else:
        conn.execute(
            "INSERT INTO feedback_votes (feedback_id, user_id, vote) VALUES (?, ?, ?)",
            (feedback_id, user_id, vote)
        )
        col = "helpful_votes" if vote == "helpful" else "not_helpful_votes"
        conn.execute(f"UPDATE feedback SET {col} = {col} + 1 WHERE id = ?", (feedback_id,))

    conn.commit()
    conn.close()


def get_rating_distribution(product_id):
    """Count of reviews per star rating (1-5) for a specific product."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT rating, COUNT(*) as count
        FROM feedback
        WHERE product_id = ?
        GROUP BY rating
    """, (product_id,)).fetchall()
    conn.close()
    dist = {i: 0 for i in range(1, 6)}
    for row in rows:
        dist[row["rating"]] = row["count"]
    return dist


def get_product_performance_scores():
    """
    Compute a 0-100 Product Performance Score for each product, combining:
      - Average rating (normalized to 100)
      - Positive sentiment ratio
      - A small bonus for review volume (more data = more trustworthy)
    """
    analytics = get_product_analytics()
    scores = []
    for p in analytics:
        if p["total"] == 0:
            scores.append({**dict(p), "performance_score": None})
            continue

        rating_component = (p["avg_rating"] / 5) * 100 if p["avg_rating"] else 0
        positive_ratio = p["positive"] / p["total"] if p["total"] else 0
        sentiment_component = positive_ratio * 100
        volume_bonus = min(p["total"] / 20, 1) * 5  # up to +5 points for 20+ reviews

        raw_score = (rating_component * 0.5) + (sentiment_component * 0.45) + volume_bonus
        performance_score = round(min(raw_score, 100), 1)
        scores.append({**dict(p), "performance_score": performance_score})

    return sorted(scores, key=lambda x: x["performance_score"] or -1, reverse=True)


def get_trending_products(limit=5):
    """Returns dicts for: most_reviewed, highest_rated, lowest_rated."""
    conn = get_connection()

    most_reviewed = conn.execute("""
        SELECT products.name, COUNT(feedback.id) as total
        FROM products
        JOIN feedback ON feedback.product_id = products.id
        GROUP BY products.id
        ORDER BY total DESC
        LIMIT ?
    """, (limit,)).fetchall()

    highest_rated = conn.execute("""
        SELECT products.name, AVG(rating) as avg_rating, COUNT(feedback.id) as total
        FROM products
        JOIN feedback ON feedback.product_id = products.id
        GROUP BY products.id
        HAVING total >= 1
        ORDER BY avg_rating DESC
        LIMIT ?
    """, (limit,)).fetchall()

    lowest_rated = conn.execute("""
        SELECT products.name, AVG(rating) as avg_rating, COUNT(feedback.id) as total
        FROM products
        JOIN feedback ON feedback.product_id = products.id
        GROUP BY products.id
        HAVING total >= 1
        ORDER BY avg_rating ASC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()
    return {
        "most_reviewed": most_reviewed,
        "highest_rated": highest_rated,
        "lowest_rated": lowest_rated
    }


def get_top_keywords(limit=10):
    """Extract top positive/negative keywords across ALL feedback text.
    Uses the sentiment module's word lists directly."""
    from sentiment import extract_keywords
    from collections import Counter

    conn = get_connection()
    rows = conn.execute("SELECT review_text FROM feedback").fetchall()
    conn.close()

    pos_counter = Counter()
    neg_counter = Counter()
    for row in rows:
        for word, polarity in extract_keywords(row["review_text"]):
            if polarity == "positive":
                pos_counter[word] += 1
            else:
                neg_counter[word] += 1

    return {
        "top_positive": pos_counter.most_common(limit),
        "top_negative": neg_counter.most_common(limit)
    }
