import os
import sys
from datetime import datetime, timedelta

import mysql.connector
import pytest
from werkzeug.security import generate_password_hash

# Point the app at the separate test database before anything connects to MySQL
os.environ["DB_NAME"] = "ecommerce_feedback_test"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ecommerce-feedback"))

import app as flask_app
from db import config, models
from nlp.sentiment import analyze_sentiment
from setup_database import SAMPLE_PRODUCTS

ADMIN_PASSWORD = "test-admin-password"
ADMIN_HASH = generate_password_hash(ADMIN_PASSWORD)
TABLES = ["recommendations", "aspect_results", "sentiment_results", "reviews", "products", "users"]


@pytest.fixture(scope="session", autouse=True)
def test_database():
    settings = config.connection_settings()
    assert settings["database"] == "ecommerce_feedback_test"
    try:
        connection = mysql.connector.connect(**settings)
    except mysql.connector.Error as error:
        pytest.exit(f"Can't reach the test database. Run setup_database.py first. ({error.msg})")
    config.apply_schema(connection)
    connection.close()


@pytest.fixture(autouse=True)
def clean_tables():
    """Each test starts with only the sample products and an admin account."""
    with config.get_cursor(commit=True) as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in TABLES:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        cursor.executemany("INSERT INTO products (name) VALUES (%s)", [(name,) for name in SAMPLE_PRODUCTS])
    models.create_user("admin", ADMIN_HASH, role="admin")


@pytest.fixture(autouse=True)
def app_settings(tmp_path):
    flask_app.app.config.update(TESTING=False, WTF_CSRF_ENABLED=False, UPLOAD_FOLDER=str(tmp_path))


@pytest.fixture
def client():
    """A test client that isn't logged in, with CSRF checks off."""
    return flask_app.app.test_client()


@pytest.fixture
def admin(client):
    """A test client logged in as the admin."""
    client.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
    return client


@pytest.fixture
def analyst():
    """A separate test client logged in as an analyst."""
    models.create_user("priya", ADMIN_HASH, role="analyst")
    analyst_client = flask_app.app.test_client()
    analyst_client.post("/login", data={"username": "priya", "password": ADMIN_PASSWORD})
    return analyst_client


def add_review(days_ago=1, rating=5, text="great product", product_id=1, customer_name="Asha"):
    """Add a review through the real analysis, dated `days_ago` days in the past."""
    return models.add_review(product_id, rating, text, analyze_sentiment(text, rating),
                             customer_name=customer_name,
                             review_date=datetime.now() - timedelta(days=days_ago))


def count_rows(table):
    with config.get_cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
        return cursor.fetchone()["total"]
