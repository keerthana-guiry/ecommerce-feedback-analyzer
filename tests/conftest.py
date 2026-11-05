import os
import sys
import tempfile

import pytest

# Importing app.py runs init_db(), so point it at a throwaway database first
os.environ["FEEDBACK_DB"] = os.path.join(tempfile.mkdtemp(), "import.db")
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ecommerce-feedback"))

import app as flask_app
import database as db


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with a fresh database and CSRF checks off."""
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.app.config.update(TESTING=False, WTF_CSRF_ENABLED=False)
    return flask_app.app.test_client()


@pytest.fixture
def customer(client):
    """A client logged in as a customer."""
    client.post("/register", data={"username": "asha", "password": "pw"})
    client.post("/login", data={"username": "asha", "password": "pw"})
    return client


def submit(client, product_id=1, rating=5, review_text="great product"):
    return client.post("/customer/feedback", data={
        "product_id": product_id, "rating": rating, "review_text": review_text
    })


def feedback_rows():
    conn = db.get_connection()
    rows = conn.execute("SELECT * FROM feedback").fetchall()
    conn.close()
    return rows
