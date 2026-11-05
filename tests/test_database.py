"""Checks that the MySQL tables enforce the rules they should."""

import mysql.connector
import pytest

from conftest import add_review, count_rows
from db import config, models
from nlp.sentiment import analyze_sentiment
from setup_database import add_starting_data


def execute(sql, params=()):
    with config.get_cursor(commit=True) as cursor:
        cursor.execute(sql, params)


def test_all_six_tables_exist():
    with config.get_cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = {list(row.values())[0] for row in cursor.fetchall()}
    assert tables == {"users", "products", "reviews", "sentiment_results",
                      "aspect_results", "recommendations"}


def test_review_and_analysis_are_stored_separately():
    review_id = add_review(text="great camera but terrible battery", rating=2)

    with config.get_cursor() as cursor:
        cursor.execute("SELECT review_text, rating FROM reviews WHERE id = %s", (review_id,))
        original = cursor.fetchone()
        cursor.execute("SELECT sentiment, model_name FROM sentiment_results WHERE review_id = %s", (review_id,))
        sentiment = cursor.fetchone()
        cursor.execute("SELECT aspect, sentiment FROM aspect_results WHERE review_id = %s", (review_id,))
        aspects = cursor.fetchall()

    assert original == {"review_text": "great camera but terrible battery", "rating": 2}
    assert sentiment == {"sentiment": "Mixed", "model_name": "rule-based-v1"}
    assert {"aspect": "Battery", "sentiment": "Negative"} in aspects


def test_a_failed_analysis_saves_nothing():
    bad_analysis = {**analyze_sentiment("great", 5), "sentiment": "Not a real sentiment"}
    with pytest.raises(mysql.connector.Error):
        models.add_review(1, 5, "great", bad_analysis)
    assert count_rows("reviews") == 0
    assert count_rows("sentiment_results") == 0


def test_deleting_a_review_removes_its_results():
    review_id = add_review(text="terrible battery", rating=1)
    assert count_rows("aspect_results") == 1
    execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    assert count_rows("sentiment_results") == 0
    assert count_rows("aspect_results") == 0


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_between_1_and_5(rating):
    with pytest.raises(mysql.connector.Error):
        execute("INSERT INTO reviews (product_id, rating, review_text, review_date) "
                "VALUES (1, %s, 'x', NOW())", (rating,))


def test_review_needs_a_real_product():
    with pytest.raises(mysql.connector.Error):
        execute("INSERT INTO reviews (product_id, rating, review_text, review_date) "
                "VALUES (999, 3, 'x', NOW())")


def test_product_with_reviews_cannot_be_deleted():
    add_review()
    with pytest.raises(mysql.connector.Error):
        execute("DELETE FROM products WHERE id = 1")


def test_usernames_are_unique():
    with pytest.raises(mysql.connector.Error):
        models.create_user("admin", "hash")


def test_role_must_be_admin_or_analyst():
    with pytest.raises(mysql.connector.Error):
        models.create_user("someone", "hash", role="customer")


def test_starting_data_creates_an_admin_only_once():
    execute("DELETE FROM users")
    connection = mysql.connector.connect(**config.connection_settings())
    try:
        assert add_starting_data(connection) is not None
        assert add_starting_data(connection) is None
    finally:
        connection.close()
    assert count_rows("users") == 1
    assert models.get_user_by_username("admin")["role"] == "admin"


def test_starting_data_does_not_duplicate_products():
    before = count_rows("products")
    connection = mysql.connector.connect(**config.connection_settings())
    try:
        add_starting_data(connection)
    finally:
        connection.close()
    assert count_rows("products") == before


def test_emoji_in_reviews_are_kept():
    review_id = add_review(text="love it 😍")
    assert models.get_review(review_id)["review_text"] == "love it 😍"
