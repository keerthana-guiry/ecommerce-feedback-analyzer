"""
Database setup for the E-Commerce Feedback Analyzer.
Uses SQLite - no server setup needed, just a local file.
"""

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

DB_NAME = "feedback.db"

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
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    conn.commit()
    conn.close()


def get_all_products():
    conn = get_connection()
    products = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return products


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
                  confidence, emotion=None, spam_score=0):
    conn = get_connection()
    conn.execute("""
        INSERT INTO feedback (user_id, product_id, rating, review_text,
                               sentiment, score, confidence, emotion,
                               spam_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, product_id, rating, review_text, sentiment, score,
          confidence, emotion, spam_score, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()


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


def get_sentiment_counts():
    conn = get_connection()
    rows = conn.execute("""
        SELECT sentiment, COUNT(*) as count
        FROM feedback
        GROUP BY sentiment
    """).fetchall()
    conn.close()
    return {row["sentiment"]: row["count"] for row in rows}


def get_feedback_over_time():
    conn = get_connection()
    rows = conn.execute("""
        SELECT substr(created_at, 1, 10) as day, sentiment, COUNT(*) as count
        FROM feedback
        GROUP BY day, sentiment
        ORDER BY day
    """).fetchall()
    conn.close()
    return rows


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
    conn.execute(
        "DELETE FROM feedback WHERE id = ? AND user_id = ?", (feedback_id, user_id)
    )
    conn.commit()
    conn.close()


def search_feedback(product_id=None, sentiment=None, username=None):
    """Admin search/filter across all feedback."""
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
    if username:
        query += " AND users.username LIKE ?"
        params.append(f"%{username}%")

    query += " ORDER BY feedback.created_at DESC"

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
