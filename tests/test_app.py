import csv
import io
import re

import mysql.connector
import pytest
from werkzeug.security import generate_password_hash

import app as flask_app
from conftest import ADMIN_PASSWORD, add_review, count_rows
from db import models

ALL_PAGES = ["/dashboard", "/analyze", "/reviews", "/reviews/export", "/products",
             "/reports", "/settings"]


# ---------- Login ----------

@pytest.mark.parametrize("path", ALL_PAGES)
def test_pages_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_and_logout(client):
    response = client.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD})
    assert response.headers["Location"].endswith("/dashboard")
    assert client.get("/dashboard").status_code == 200

    client.get("/logout")
    assert client.get("/dashboard").status_code == 302


def test_wrong_password_is_rejected(client):
    response = client.post("/login", data={"username": "admin", "password": "wrong"})
    assert b"Invalid username or password" in response.data
    assert client.get("/dashboard").status_code == 302


def test_old_default_admin_password_does_not_work(client):
    client.post("/login", data={"username": "admin", "password": "admin123"})
    assert client.get("/dashboard").status_code == 302


def test_login_page_does_not_show_any_password(client):
    assert b"admin123" not in client.get("/login").data


def test_analyst_can_log_in_and_open_pages(client):
    models.create_user("priya", generate_password_hash("pw"), role="analyst")
    client.post("/login", data={"username": "priya", "password": "pw"})
    assert client.get("/dashboard").status_code == 200
    assert "Analyst".lower() in client.get("/settings").data.decode().lower()


# ---------- Removed customer features ----------

@pytest.mark.parametrize("path", ["/register", "/customer/feedback", "/customer/history",
                                  "/customer/edit/1", "/admin/sentiment"])
def test_old_customer_and_admin_urls_are_gone(admin, path):
    assert admin.get(path).status_code == 404


def test_login_page_has_no_registration_link(client):
    assert b"Register" not in client.get("/login").data


# ---------- Pages ----------

@pytest.mark.parametrize("path, text", [
    ("/dashboard", "Top-Performing Products"),
    ("/analyze", "Submit a Review"),
    ("/reviews", "Customer Reviews"),
    ("/products", "Sentiment by Product"),
    ("/reports", "Product Performance Comparison"),
    ("/reports?view=weekly", "Product Performance Comparison"),
    ("/reports?view=monthly", "Product Performance Comparison"),
    ("/reports?view=bogus", "Product Performance Comparison"),
    ("/settings", "User Profile"),
])
def test_pages_render_with_data(admin, path, text):
    add_review(text="great camera but terrible battery", rating=2)
    response = admin.get(path)
    assert response.status_code == 200
    assert text in response.data.decode()


@pytest.mark.parametrize("path", ALL_PAGES)
def test_pages_render_with_no_reviews(admin, path):
    assert admin.get(path).status_code == 200


def test_dashboard_says_when_there_are_no_reviews(admin):
    assert b"No reviews in this period." in admin.get("/dashboard").data


def test_recommendations_are_not_made_up(admin):
    add_review()
    assert "Phase 7" in admin.get("/dashboard").data.decode()
    assert count_rows("recommendations") == 0


@pytest.mark.parametrize("query, selected", [
    ("?days=7", "Last 7 days"), ("?days=90", "Last 90 days"),
    ("?days=12345", "Last 30 days"), ("?days=abc", "Last 30 days"), ("", "Last 30 days"),
])
def test_dashboard_period_option(admin, query, selected):
    page = admin.get("/dashboard" + query).data.decode()
    assert re.search(r"<option[^>]*selected>" + selected, page)


def test_database_outage_shows_a_friendly_page(admin, monkeypatch):
    def fail(*args, **kwargs):
        raise mysql.connector.Error("MySQL is down")
    monkeypatch.setattr(models, "get_dashboard_data", fail)

    response = admin.get("/dashboard")
    assert response.status_code == 503
    assert b"reach the database" in response.data
    assert b"MySQL is down" not in response.data


# ---------- Dashboard and trend data ----------

def kpi(data, label):
    return next(k for k in data["kpis"] if k["label"] == label)


def test_dashboard_compares_against_the_previous_period():
    for _ in range(3):
        add_review(1, rating=5, text="excellent product")
    add_review(2, rating=1, text="terrible awful product")
    add_review(40, rating=3, text="great product")
    add_review(45, rating=3, text="it is okay")
    add_review(100)  # too old for either period

    data = models.get_dashboard_data(30)

    assert data["total"] == 4
    assert len(data["labels"]) == 30
    assert kpi(data, "Total Reviews")["change"] == 100.0
    assert kpi(data, "Average Rating")["value"] == "4.00"
    assert kpi(data, "Average Rating")["change"] == 1.0
    assert kpi(data, "Positive")["value"] == "75.0%"
    assert kpi(data, "Positive")["change"] == 25.0
    assert kpi(data, "Negative")["value"] == "25.0%"
    assert kpi(data, "Negative")["change"] == 25.0
    assert kpi(data, "Neutral")["change"] == -50.0
    assert data["distribution"] == {"Positive": 3, "Neutral": 0, "Mixed": 0, "Negative": 1}


def test_dashboard_with_no_reviews():
    data = models.get_dashboard_data(7)
    assert data["total"] == 0
    assert kpi(data, "Average Rating")["value"] == "—"
    assert kpi(data, "Total Reviews")["change"] is None


def test_review_on_the_oldest_day_of_the_period_counts():
    add_review(29)
    add_review(30)
    data = models.get_dashboard_data(30)
    assert data["total"] == 1
    assert kpi(data, "Total Reviews")["change"] == 0.0


def test_future_dated_review_is_not_counted():
    add_review(-5)
    assert models.get_dashboard_data(30)["total"] == 0


@pytest.mark.parametrize("view, periods", [("daily", 30), ("weekly", 12), ("monthly", 12)])
def test_sentiment_trend_buckets(view, periods):
    add_review(0, rating=5, text="excellent product")
    add_review(0, rating=1, text="terrible awful product")
    trend = models.get_sentiment_trend(view)

    assert len(trend["labels"]) == periods
    assert trend["total"] == 2
    assert trend["sentiment_series"]["Positive"][-1] == 1
    assert trend["sentiment_series"]["Negative"][-1] == 1
    assert trend["positive_rate"][-1] == 50.0
    assert trend["avg_rating"][-1] == 3.0
    assert trend["positive_rate"][0] is None  # no reviews yet, so no made-up value


def test_monthly_trend_reaches_back_almost_a_year():
    add_review(330)
    assert models.get_sentiment_trend("monthly")["total"] == 1


def test_product_scores_use_plain_numbers_for_charts(admin):
    add_review(rating=4)
    product = next(p for p in models.get_product_performance_scores() if p["total"])
    assert type(product["positive"]) is int
    assert type(product["avg_rating"]) is float
    assert b'"avg_rating": 4.0' in admin.get("/products").data or b'"avg_rating":4.0' in admin.get("/products").data


def test_trending_products():
    add_review(rating=5, product_id=1)
    add_review(rating=1, product_id=2)
    add_review(rating=1, product_id=2)
    trending = models.get_trending_products()
    assert trending["most_reviewed"][0]["total"] == 2
    assert trending["highest_rated"][0]["avg_rating"] == 5
    assert trending["lowest_rated"][0]["avg_rating"] == 1


# ---------- Review Analysis ----------

def submit(client, **overrides):
    data = {"product_id": 1, "rating": 2, "review_text": "great camera but terrible battery"}
    data.update(overrides)
    return client.post("/analyze", data=data, follow_redirects=True)


def test_analyze_saves_the_review_and_shows_stored_results(admin):
    page = submit(admin, customer_name="Asha").data.decode()

    review = models.search_reviews()[0]
    assert count_rows("reviews") == 1
    assert review["sentiment"] == "Mixed"
    assert review["customer_name"] == "Asha"
    assert review["source"] == "manual"
    assert "great camera but terrible battery" in page
    assert "Battery: Negative" in page


def test_analyze_without_a_customer_name(admin):
    submit(admin)
    assert models.search_reviews()[0]["customer_name"] is None
    assert "Anonymous" in admin.get("/reviews").data.decode()


@pytest.mark.parametrize("field, value, message", [
    ("rating", 99, "rating from 1 to 5"),
    ("rating", 0, "rating from 1 to 5"),
    ("rating", "abc", "rating from 1 to 5"),
    ("product_id", 999, "valid product"),
    ("product_id", "abc", "valid product"),
    ("review_text", "   ", "enter the review text"),
    ("customer_name", "x" * 101, "at most 100 characters"),
])
def test_analyze_rejects_bad_input(admin, field, value, message):
    response = submit(admin, **{field: value})
    assert message in response.data.decode()
    assert count_rows("reviews") == 0


def test_review_text_is_escaped_on_every_page(admin):
    submit(admin, review_text="<script>alert(1)</script>", customer_name="<b>x</b>")
    for path in ["/reviews", "/dashboard", "/analyze?review=1"]:
        page = admin.get(path).data.decode()
        assert "<script>alert(1)</script>" not in page
        assert "<b>x</b>" not in page


def test_unknown_review_id_shows_the_empty_form(admin):
    response = admin.get("/analyze?review=999")
    assert response.status_code == 200
    assert b"Submit a review to see its analysis" in response.data


# ---------- All Reviews ----------

@pytest.fixture
def sample_reviews():
    add_review(1, rating=5, text="excellent product", customer_name="Asha")
    add_review(2, rating=5, text="excellent value", customer_name="Ravi")
    add_review(3, rating=1, text="a needle in terrible awful packaging", product_id=2, customer_name="Meera")


@pytest.mark.parametrize("query, expected_count", [
    ("search=needle", 1),
    ("search=NEEDLE", 1),
    ("search=meera", 1),
    ("rating=1", 1),
    ("rating=5", 2),
    ("sentiment=Negative", 1),
    ("product_id=2", 1),
    ("rating=abc", 3),
    ("product_id=abc", 3),
    ("search=%25", 0),
    ("search=_", 0),
    ("search=nothing-matches", 0),
    ("sentiment=Positive&rating=5&product_id=1", 2),
])
def test_review_filters(admin, sample_reviews, query, expected_count):
    page = admin.get("/reviews?" + query).data.decode()
    if expected_count:
        assert f"of {expected_count} results" in page
    else:
        assert "No reviews match" in page


@pytest.mark.parametrize("attack", ["' OR 1=1 --", "'; DROP TABLE reviews; --", "\" OR \"\"=\""])
def test_review_search_is_not_sql_injectable(admin, sample_reviews, attack):
    response = admin.get("/reviews", query_string={"search": attack})
    assert response.status_code == 200
    assert b"No reviews match" in response.data
    assert count_rows("reviews") == 3


def test_sentiment_filter_is_not_sql_injectable(admin, sample_reviews):
    response = admin.get("/reviews", query_string={"sentiment": "x' OR '1'='1"})
    assert b"No reviews match" in response.data


def test_review_sort_by_date(admin):
    add_review(5, rating=2, text="older")
    add_review(1, rating=4, text="newer")
    assert models.search_reviews()[0]["review_text"] == "newer"
    assert models.search_reviews(oldest_first=True)[0]["review_text"] == "older"
    assert 'value="oldest" selected' in admin.get("/reviews?sort=oldest").data.decode()


def test_pagination_keeps_filters(admin):
    for _ in range(12):
        add_review(1, text="excellent product", rating=5)
    add_review(1, text="terrible awful product", rating=1)

    first = admin.get("/reviews?sentiment=Positive").data.decode()
    assert "Showing 1 to 10 of 12 results" in first
    assert "page=2&amp;sentiment=Positive" in first or "sentiment=Positive&amp;page=2" in first

    second = admin.get("/reviews?sentiment=Positive&page=2").data.decode()
    assert "Showing 11 to 12 of 12 results" in second


@pytest.mark.parametrize("page_value, shown", [("999", "Showing 11 to 11"), ("0", "Showing 1 to 10"),
                                               ("abc", "Showing 1 to 10")])
def test_page_number_is_kept_in_range(admin, page_value, shown):
    for _ in range(11):
        add_review(1)
    assert shown in admin.get(f"/reviews?page={page_value}").data.decode()


# ---------- CSV export ----------

def exported_rows(client):
    return list(csv.reader(io.StringIO(client.get("/reviews/export").data.decode())))


def test_export_includes_each_review_and_its_analysis(admin):
    add_review(rating=5, text="excellent product", customer_name="Asha")
    header, row = exported_rows(admin)
    assert row[header.index("Customer")] == "Asha"
    assert row[header.index("Review")] == "excellent product"
    assert row[header.index("Sentiment")] == "Positive"


@pytest.mark.parametrize("text", ["=1+1", "+cmd", "-2+3", "@SUM(A1)"])
def test_export_stops_formulas_running_in_spreadsheets(admin, text):
    add_review(text=text)
    header, row = exported_rows(admin)
    assert row[header.index("Review")] == "'" + text


# ---------- Form protection ----------

def test_post_without_csrf_token_is_rejected(admin):
    flask_app.app.config["WTF_CSRF_ENABLED"] = True
    response = admin.post("/analyze", data={"product_id": 1, "rating": 5, "review_text": "x"})
    assert response.status_code == 400
    assert count_rows("reviews") == 0


def test_post_with_csrf_token_is_accepted(admin):
    flask_app.app.config["WTF_CSRF_ENABLED"] = True
    page = admin.get("/analyze").data.decode()
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = admin.post("/analyze", data={"product_id": 1, "rating": 5, "review_text": "x",
                                            "csrf_token": token})
    assert response.status_code == 302
    assert count_rows("reviews") == 1
