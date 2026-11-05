import re
from datetime import datetime, timedelta

import pytest

import app as flask_app
import database as db
from conftest import feedback_rows, submit


def test_submit_valid_feedback(customer):
    assert submit(customer).status_code == 302
    assert len(feedback_rows()) == 1


@pytest.mark.parametrize("rating", ["abc", "", 0, 6, 99])
def test_invalid_rating_is_rejected(customer, rating):
    response = submit(customer, rating=rating)
    assert response.status_code == 200
    assert b"rating from 1 to 5" in response.data
    assert feedback_rows() == []


@pytest.mark.parametrize("product_id", ["abc", "", 999])
def test_invalid_product_is_rejected(customer, product_id):
    response = submit(customer, product_id=product_id)
    assert response.status_code == 200
    assert b"valid product" in response.data
    assert feedback_rows() == []


def test_edit_page_loads_and_saves(customer):
    submit(customer)
    assert customer.get("/customer/edit/1").status_code == 200

    customer.post("/customer/edit/1", data={"rating": 1, "review_text": "terrible"})
    row = feedback_rows()[0]
    assert (row["rating"], row["sentiment"]) == (1, "Negative")


def test_edit_rejects_invalid_rating(customer):
    submit(customer)
    response = customer.post("/customer/edit/1", data={"rating": 99, "review_text": "bad"})
    assert response.status_code == 200
    assert feedback_rows()[0]["rating"] == 5


def test_cannot_edit_someone_elses_feedback(customer):
    submit(customer)
    customer.get("/logout")
    customer.post("/register", data={"username": "ravi", "password": "pw"})
    customer.post("/login", data={"username": "ravi", "password": "pw"})

    customer.post("/customer/edit/1", data={"rating": 1, "review_text": "hacked"})
    assert feedback_rows()[0]["review_text"] == "great product"


def test_delete_removes_votes_too(customer):
    submit(customer)
    customer.post("/feedback/vote/1/helpful")
    customer.post("/customer/delete/1")

    conn = db.get_connection()
    votes = conn.execute("SELECT COUNT(*) FROM feedback_votes").fetchone()[0]
    conn.close()
    assert feedback_rows() == []
    assert votes == 0


def test_cannot_delete_someone_elses_feedback_or_its_votes(customer):
    submit(customer)
    customer.post("/feedback/vote/1/helpful")
    customer.get("/logout")
    customer.post("/register", data={"username": "ravi", "password": "pw"})
    customer.post("/login", data={"username": "ravi", "password": "pw"})
    customer.post("/customer/delete/1")

    conn = db.get_connection()
    votes = conn.execute("SELECT COUNT(*) FROM feedback_votes").fetchone()[0]
    conn.close()
    assert len(feedback_rows()) == 1
    assert votes == 1


def test_vote_on_missing_feedback_is_ignored(customer):
    customer.post("/feedback/vote/999/helpful")
    conn = db.get_connection()
    votes = conn.execute("SELECT COUNT(*) FROM feedback_votes").fetchone()[0]
    conn.close()
    assert votes == 0


def test_voting_twice_counts_once_and_can_change(customer):
    submit(customer)
    customer.post("/feedback/vote/1/helpful")
    customer.post("/feedback/vote/1/helpful")
    assert feedback_rows()[0]["helpful_votes"] == 1

    customer.post("/feedback/vote/1/not_helpful")
    row = feedback_rows()[0]
    assert (row["helpful_votes"], row["not_helpful_votes"]) == (0, 1)


def test_customer_cannot_open_admin_pages(customer):
    for path in ["/admin/sentiment", "/admin/products", 
                 "/admin/feedback", "/admin/export", "/admin/reports"]:
        response = customer.get(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


def test_admin_pages_load_with_data(customer):
    submit(customer)
    customer.get("/logout")
    customer.post("/login", data={"username": "admin", "password": "test-admin-password"})
    for path in ["/admin/sentiment", "/admin/products", 
                 "/admin/feedback", "/admin/export", "/admin/reports"]:
        assert customer.get(path).status_code == 200


def add_review(days_ago, rating=5, sentiment="Positive", spam_score=0):
    when = datetime.now() - timedelta(days=days_ago)
    db.add_feedback(1, 1, rating, "text", sentiment, 1, 50, None, spam_score,
                    created_at=when.strftime("%Y-%m-%d %H:%M"))


def kpi(data, label):
    return next(k for k in data["kpis"] if k["label"] == label)


def test_dashboard_compares_against_the_previous_period(client):
    for _ in range(3):
        add_review(1)
    add_review(2, rating=1, sentiment="Negative", spam_score=60)
    add_review(40, rating=3, sentiment="Positive")
    add_review(45, rating=3, sentiment="Neutral")
    add_review(100)  # too old for either period

    data = db.get_dashboard_data(30)

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


@pytest.mark.parametrize("view, periods", [("daily", 30), ("weekly", 12), ("monthly", 12)])
def test_sentiment_trend_buckets(client, view, periods):
    add_review(0)
    add_review(0, rating=1, sentiment="Negative")
    trend = db.get_sentiment_trend(view)

    assert len(trend["labels"]) == periods
    assert trend["total"] == 2
    assert trend["sentiment_series"]["Positive"][-1] == 1
    assert trend["sentiment_series"]["Negative"][-1] == 1
    assert trend["positive_rate"][-1] == 50.0
    assert trend["avg_rating"][-1] == 3.0
    assert trend["positive_rate"][0] is None  # no reviews yet, so no made-up value


def test_monthly_trend_groups_a_whole_month_across_a_year_boundary(client):
    # 11 months back from any date is always inside the 12 month window
    add_review(330)
    trend = db.get_sentiment_trend("monthly")
    assert trend["total"] == 1


def test_dashboard_with_no_reviews(client):
    data = db.get_dashboard_data(7)
    assert data["total"] == 0
    assert kpi(data, "Average Rating")["value"] == "—"
    assert kpi(data, "Total Reviews")["change"] is None


def test_review_on_the_oldest_day_of_the_period_counts(client):
    add_review(29)
    add_review(30)
    data = db.get_dashboard_data(30)
    assert data["total"] == 1
    assert kpi(data, "Total Reviews")["change"] == 0.0


@pytest.fixture
def admin(customer):
    customer.get("/logout")
    customer.post("/login", data={"username": "admin", "password": "test-admin-password"})
    return customer


@pytest.mark.parametrize("path, text", [
    ("/admin/sentiment", "Top-Performing Products"),
    ("/admin/analyze", "Submit a Review"),
    ("/admin/feedback", "Customer Reviews"),
    ("/admin/products", "Sentiment by Product"),
    ("/admin/reports", "Product Performance Comparison"),
    ("/admin/reports?view=weekly", "Product Performance Comparison"),
    ("/admin/reports?view=monthly", "Product Performance Comparison"),
    ("/admin/reports?view=bogus", "Product Performance Comparison"),
    ("/settings", "User Profile"),
])
def test_admin_pages_render(admin, path, text):
    add_review(1)
    response = admin.get(path)
    assert response.status_code == 200
    assert text in response.data.decode()


def test_customer_can_open_settings(customer):
    assert customer.get("/settings").status_code == 200


def test_analyze_saves_the_review_and_shows_its_result(admin):
    response = admin.post("/admin/analyze", data={
        "product_id": 1, "rating": 2, "review_text": "great camera but terrible battery"
    }, follow_redirects=True)
    page = response.data.decode()

    assert len(feedback_rows()) == 1
    assert feedback_rows()[0]["sentiment"] == "Mixed"
    assert "great camera but terrible battery" in page
    assert "Battery: Negative" in page


@pytest.mark.parametrize("field, value, message", [
    ("rating", 99, "rating from 1 to 5"),
    ("product_id", 999, "valid product"),
    ("review_text", "   ", "enter the review text"),
])
def test_analyze_rejects_bad_input(admin, field, value, message):
    data = {"product_id": 1, "rating": 3, "review_text": "fine"}
    data[field] = value
    response = admin.post("/admin/analyze", data=data)
    assert message in response.data.decode()
    assert feedback_rows() == []


def test_customer_cannot_open_new_admin_pages(customer):
    for path in ["/admin/analyze", "/admin/reports"]:
        assert customer.get(path).status_code == 302


@pytest.mark.parametrize("query, expected_count", [
    ("search=needle", 1),
    ("search=NEEDLE", 1),
    ("rating=1", 1),
    ("rating=5", 2),
    ("sentiment=Negative", 1),
    ("rating=abc", 3),
    ("search=%25", 3),
    ("search=nothing-matches", 0),
])
def test_review_filters(admin, query, expected_count):
    add_review(1)
    add_review(2)
    db.add_feedback(1, 2, 1, "a needle in here", "Negative", -1, 50)
    page = admin.get("/admin/feedback?" + query).data.decode()
    if expected_count:
        assert f"of {expected_count} results" in page
    else:
        assert "No reviews match" in page


def test_review_search_is_not_sql_injectable(admin):
    add_review(1)
    response = admin.get("/admin/feedback", query_string={"search": "' OR 1=1 --"})
    assert response.status_code == 200
    assert b"No reviews match" in response.data


def test_review_sort_by_date(admin):
    add_review(5, rating=2)
    add_review(1, rating=4)
    assert db.search_feedback()[0]["rating"] == 4
    assert db.search_feedback(oldest_first=True)[0]["rating"] == 2
    assert 'value="oldest" selected' in admin.get("/admin/feedback?sort=oldest").data.decode()


def test_recommendations_are_not_made_up(admin):
    add_review(1)
    page = admin.get("/admin/sentiment").data.decode()
    assert "Phase 7" in page


@pytest.mark.parametrize("query, selected", [
    ("?days=7", "Last 7 days"), ("?days=90", "Last 90 days"),
    ("?days=12345", "Last 30 days"), ("?days=abc", "Last 30 days"), ("", "Last 30 days"),
])
def test_overview_period_option(admin, query, selected):
    page = admin.get("/admin/sentiment" + query).data.decode()
    assert re.search(r"<option[^>]*selected>" + selected, page)


def test_overview_loads_with_no_reviews(admin):
    response = admin.get("/admin/sentiment")
    assert response.status_code == 200
    assert b"No reviews in this period." in response.data


def test_feedback_pagination_keeps_filters(admin):
    for _ in range(12):
        add_review(1)
    add_review(1, sentiment="Negative")

    first = admin.get("/admin/feedback?sentiment=Positive").data.decode()
    assert "Showing 1 to 10 of 12 results" in first
    assert "page=2&amp;sentiment=Positive" in first or "sentiment=Positive&amp;page=2" in first

    second = admin.get("/admin/feedback?sentiment=Positive&page=2").data.decode()
    assert "Showing 11 to 12 of 12 results" in second


@pytest.mark.parametrize("page_value, shown", [("999", "Showing 11 to 11"), ("0", "Showing 1 to 10"),
                                               ("abc", "Showing 1 to 10")])
def test_feedback_page_number_is_kept_in_range(admin, page_value, shown):
    for _ in range(11):
        add_review(1)
    assert shown in admin.get(f"/admin/feedback?page={page_value}").data.decode()


def test_old_default_admin_password_is_gone(client):
    client.post("/login", data={"username": "admin", "password": "admin123"})
    assert client.get("/admin/sentiment").status_code == 302


def test_login_page_does_not_show_admin_password(client):
    assert b"admin123" not in client.get("/login").data


def test_generated_admin_password_when_none_is_set(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(db, "DB_NAME", str(tmp_path / "fresh.db"))
    monkeypatch.delenv("ADMIN_PASSWORD")
    db.init_db()
    assert "Created admin account" in capsys.readouterr().out

    # Running it again must not create or print a new password
    db.init_db()
    assert capsys.readouterr().out == ""


def test_post_without_csrf_token_is_rejected(client):
    flask_app.app.config["WTF_CSRF_ENABLED"] = True
    response = client.post("/register", data={"username": "x", "password": "y"})
    assert response.status_code == 400
    assert db.get_user_by_username("x") is None


def test_post_with_csrf_token_is_accepted(client):
    flask_app.app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/register").data.decode()
    token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
    response = client.post("/register", data={"username": "x", "password": "y", "csrf_token": token})
    assert response.status_code == 302
    assert db.get_user_by_username("x") is not None
