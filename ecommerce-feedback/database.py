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
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
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


def add_feedback(user_id, product_id, rating, review_text, sentiment, score, confidence):
    conn = get_connection()
    conn.execute("""
        INSERT INTO feedback (user_id, product_id, rating, review_text,
                               sentiment, score, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, product_id, rating, review_text, sentiment, score,
          confidence, datetime.now().strftime("%Y-%m-%d %H:%M")))
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


def update_feedback(feedback_id, rating, review_text, sentiment, score, confidence):
    conn = get_connection()
    conn.execute("""
        UPDATE feedback
        SET rating = ?, review_text = ?, sentiment = ?, score = ?, confidence = ?
        WHERE id = ?
    """, (rating, review_text, sentiment, score, confidence, feedback_id))
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
