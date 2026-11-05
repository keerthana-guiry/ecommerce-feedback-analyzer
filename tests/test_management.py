"""Tests for Phase 3: roles, accounts, review editing and deleting, and CSV upload."""

import io
import os
from datetime import datetime, timedelta

import pytest
from werkzeug.security import check_password_hash

import app as flask_app
from conftest import ADMIN_PASSWORD, add_review, count_rows
from db import models
from nlp.sentiment import analyze_sentiment

NEW_PASSWORD = "a-new-password"
PRODUCT = "Laptop Backpack"


def login(username, password):
    client = flask_app.app.test_client()
    client.post("/login", data={"username": username, "password": password})
    return client


def is_logged_in(client):
    return client.get("/settings").status_code == 200


def analyst_id():
    return models.get_user_by_username("priya")["id"]


def add_analyst_review():
    return models.add_review(1, 5, "great product", analyze_sentiment("great product", 5),
                             submitted_by=analyst_id(), customer_name="Asha")


# ---------- What each role can do ----------

@pytest.mark.parametrize("path, data", [
    ("/settings/users", {"username": "sneaky", "password": NEW_PASSWORD, "role": "admin"}),
    ("/settings/users/1/password", {"password": NEW_PASSWORD}),
    ("/settings/users/1/delete", {}),
    ("/products", {"name": "Sneaky Product"}),
])
def test_analysts_cannot_use_admin_actions(analyst, path, data):
    products_before = count_rows("products")
    users_before = count_rows("users")
    assert analyst.post(path, data=data).status_code == 403
    assert count_rows("products") == products_before
    assert count_rows("users") == users_before
    assert check_password_hash(models.get_user_by_id(1)["password_hash"], ADMIN_PASSWORD)


@pytest.mark.parametrize("path", ["/settings/users", "/settings/users/1/delete", "/products",
                                  "/reviews/upload", "/reviews/1/delete", "/settings/password"])
def test_actions_require_login(client, path):
    response = client.post(path)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert count_rows("users") == 1


def test_only_admins_see_admin_sections(admin, analyst):
    assert b"User Accounts" in admin.get("/settings").data
    assert b"User Accounts" not in analyst.get("/settings").data
    assert b"Add a Product" in admin.get("/products").data
    assert b"Add a Product" not in analyst.get("/products").data


# ---------- Managing accounts ----------

def test_admin_creates_an_account_that_can_log_in(admin):
    admin.post("/settings/users", data={"username": "ravi", "password": NEW_PASSWORD, "role": "analyst"})
    assert models.get_user_by_username("ravi")["role"] == "analyst"
    assert is_logged_in(login("ravi", NEW_PASSWORD))


def test_passwords_are_stored_hashed(admin):
    admin.post("/settings/users", data={"username": "ravi", "password": NEW_PASSWORD, "role": "analyst"})
    assert NEW_PASSWORD not in models.get_user_by_username("ravi")["password_hash"]
    assert NEW_PASSWORD.encode() not in admin.get("/settings").data


@pytest.mark.parametrize("data, message", [
    ({"username": "ab", "password": NEW_PASSWORD, "role": "analyst"}, "3 to 50 letters"),
    ({"username": "has space", "password": NEW_PASSWORD, "role": "analyst"}, "3 to 50 letters"),
    ({"username": "<b>x</b>", "password": NEW_PASSWORD, "role": "analyst"}, "3 to 50 letters"),
    ({"username": "ravi", "password": "short", "role": "analyst"}, "8 to 128 characters"),
    ({"username": "ravi", "password": NEW_PASSWORD, "role": "customer"}, "choose a role"),
    ({"username": "ADMIN", "password": NEW_PASSWORD, "role": "analyst"}, "already taken"),
])
def test_bad_new_accounts_are_rejected(admin, data, message):
    response = admin.post("/settings/users", data=data, follow_redirects=True)
    assert message in response.data.decode()
    assert count_rows("users") == 1


def test_admin_cannot_delete_their_own_account(admin):
    response = admin.post("/settings/users/1/delete", follow_redirects=True)
    assert b"delete your own account" in response.data
    assert count_rows("users") == 1


def test_deleting_an_account_keeps_its_reviews_and_logs_it_out(admin, analyst):
    review_id = add_analyst_review()
    assert is_logged_in(analyst)

    admin.post(f"/settings/users/{analyst_id()}/delete")

    assert not is_logged_in(analyst)
    assert models.get_review(review_id)["submitted_by"] is None


def test_admin_reset_changes_the_password_and_logs_the_user_out(admin, analyst):
    user_id = analyst_id()
    admin.post(f"/settings/users/{user_id}/password", data={"password": NEW_PASSWORD})
    assert not is_logged_in(analyst)
    assert not is_logged_in(login("priya", ADMIN_PASSWORD))
    assert is_logged_in(login("priya", NEW_PASSWORD))


def test_admin_cannot_reset_their_own_password_without_the_current_one(admin):
    admin.post("/settings/users/1/password", data={"password": NEW_PASSWORD})
    assert check_password_hash(models.get_user_by_id(1)["password_hash"], ADMIN_PASSWORD)


def test_reset_rejects_a_short_password_and_unknown_accounts(admin, analyst):
    admin.post(f"/settings/users/{analyst_id()}/password", data={"password": "short"})
    assert is_logged_in(analyst)
    assert admin.get("/settings/users/999/password").status_code == 404


# ---------- Your own account ----------

def change_password(client, current=ADMIN_PASSWORD, new=NEW_PASSWORD, confirm=None):
    return client.post("/settings/password", follow_redirects=True, data={
        "current_password": current, "new_password": new,
        "confirm_password": new if confirm is None else confirm})


def test_changing_your_password(admin):
    other_device = login("admin", ADMIN_PASSWORD)

    change_password(admin)

    assert is_logged_in(admin)
    assert not is_logged_in(other_device)
    assert not is_logged_in(login("admin", ADMIN_PASSWORD))
    assert is_logged_in(login("admin", NEW_PASSWORD))


@pytest.mark.parametrize("kwargs, message", [
    ({"current": "wrong"}, "current password"),
    ({"confirm": "different-password"}, "didn&#39;t match"),
    ({"new": "short"}, "8 to 128 characters"),
])
def test_bad_password_changes_are_rejected(admin, kwargs, message):
    assert message in change_password(admin, **kwargs).data.decode()
    assert check_password_hash(models.get_user_by_id(1)["password_hash"], ADMIN_PASSWORD)


def test_changing_your_username(admin):
    admin.post("/settings/profile", data={"username": "new.name"})
    assert b"new.name" in admin.get("/settings").data
    assert is_logged_in(login("new.name", ADMIN_PASSWORD))


def test_username_already_taken(admin, analyst):
    response = admin.post("/settings/profile", data={"username": "priya"}, follow_redirects=True)
    assert b"already taken" in response.data
    assert models.get_user_by_id(1)["username"] == "admin"


def test_default_time_period_preference(admin):
    admin.post("/settings/preferences", data={"default_days": 90})
    assert '<option value="90" selected>' in admin.get("/dashboard").data.decode()
    assert '<option value="7" selected>' in admin.get("/dashboard?days=7").data.decode()


def test_bad_time_period_preference_is_rejected(admin):
    response = admin.post("/settings/preferences", data={"default_days": 5}, follow_redirects=True)
    assert b"listed time periods" in response.data
    assert models.get_user_by_id(1)["default_days"] == 30


# ---------- Editing and deleting reviews ----------

def test_editing_replaces_the_old_analysis(admin):
    review_id = add_review(rating=5, text="excellent battery", customer_name="Asha")
    assert models.get_review(review_id)["sentiment"] == "Positive"

    response = admin.post(f"/reviews/{review_id}/edit", follow_redirects=True, data={
        "product_id": 2, "rating": 1, "review_text": "terrible awful camera", "customer_name": ""})

    review = models.get_review(review_id)
    assert b"analyzed again" in response.data
    assert review["sentiment"] == "Negative"
    assert review["product_id"] == 2
    assert review["customer_name"] is None
    assert [aspect["aspect"] for aspect in review["aspects"]] == ["Camera"]
    assert count_rows("sentiment_results") == 1


def test_editing_keeps_the_original_date_and_submitter(admin, analyst):
    review_id = add_analyst_review()
    before = models.get_review(review_id)
    admin.post(f"/reviews/{review_id}/edit", data={"product_id": 1, "rating": 2, "review_text": "changed"})
    after = models.get_review(review_id)
    assert after["review_date"] == before["review_date"]
    assert after["submitted_by"] == before["submitted_by"]


@pytest.mark.parametrize("field, value, message", [
    ("rating", 9, "rating from 1 to 5"),
    ("product_id", 999, "valid product"),
    ("review_text", "   ", "enter the review text"),
    ("review_text", "x" * 5001, "at most 5000 characters"),
    ("customer_name", "x" * 101, "at most 100 characters"),
])
def test_bad_edits_change_nothing(admin, field, value, message):
    review_id = add_review(text="original text")
    data = {"product_id": 1, "rating": 5, "review_text": "new text", field: value}
    response = admin.post(f"/reviews/{review_id}/edit", data=data)
    assert message in response.data.decode()
    assert models.get_review(review_id)["review_text"] == "original text"


def test_edit_form_shows_the_current_review(admin):
    review_id = add_review(text="<script>original</script>")
    page = admin.get(f"/reviews/{review_id}/edit").data.decode()
    assert "&lt;script&gt;original&lt;/script&gt;" in page
    assert "<script>original" not in page


def test_deleting_removes_the_review_and_its_analysis(admin):
    review_id = add_review(text="terrible battery", rating=1)
    admin.post(f"/reviews/{review_id}/delete")
    assert models.get_review(review_id) is None
    assert count_rows("sentiment_results") == 0
    assert count_rows("aspect_results") == 0


def test_delete_returns_to_the_same_page_and_filters(admin):
    review_id = add_review()
    response = admin.post(f"/reviews/{review_id}/delete?page=2&sentiment=Positive")
    assert "page=2" in response.headers["Location"]
    assert "sentiment=Positive" in response.headers["Location"]


def test_delete_needs_post(admin):
    review_id = add_review()
    assert admin.get(f"/reviews/{review_id}/delete").status_code == 405
    assert models.get_review(review_id)


@pytest.mark.parametrize("path, method", [("/reviews/999/edit", "get"), ("/reviews/999/delete", "post")])
def test_unknown_review_is_not_found(admin, path, method):
    assert getattr(admin, method)(path).status_code == 404


def test_analyst_can_manage_their_own_reviews(analyst):
    review_id = add_analyst_review()
    assert analyst.get(f"/reviews/{review_id}/edit").status_code == 200
    analyst.post(f"/reviews/{review_id}/delete")
    assert models.get_review(review_id) is None


def test_analyst_cannot_change_other_peoples_reviews(analyst):
    review_id = add_review(text="someone else's review")
    data = {"product_id": 1, "rating": 1, "review_text": "tampered"}
    assert analyst.get(f"/reviews/{review_id}/edit").status_code == 403
    assert analyst.post(f"/reviews/{review_id}/edit", data=data).status_code == 403
    assert analyst.post(f"/reviews/{review_id}/delete").status_code == 403
    assert models.get_review(review_id)["review_text"] == "someone else's review"


def test_actions_only_show_on_reviews_you_can_change(admin, analyst):
    own_id = add_analyst_review()
    other_id = add_review(text="not theirs")
    page = analyst.get("/reviews").data.decode()
    assert f"/reviews/{own_id}/edit" in page
    assert f"/reviews/{other_id}/edit" not in page
    assert f"/reviews/{other_id}/edit" in admin.get("/reviews").data.decode()


def test_manual_reviews_record_who_submitted_them(analyst):
    analyst.post("/analyze", data={"product_id": 1, "rating": 5, "review_text": "nice"})
    assert models.search_reviews()[0]["submitted_by"] == analyst_id()


def test_manual_review_length_limit(admin):
    response = admin.post("/analyze", data={"product_id": 1, "rating": 5, "review_text": "x" * 5001})
    assert b"at most 5000 characters" in response.data
    assert count_rows("reviews") == 0


# ---------- Adding products ----------

def test_admin_adds_a_product(admin):
    admin.post("/products", data={"name": "  Desk Lamp  "})
    assert any(product["name"] == "Desk Lamp" for product in models.get_all_products())


@pytest.mark.parametrize("name, message", [
    ("", "enter a product name"),
    ("x" * 151, "at most 150 characters"),
    (PRODUCT.upper(), "already exists"),
])
def test_bad_products_are_rejected(admin, name, message):
    before = count_rows("products")
    response = admin.post("/products", data={"name": name}, follow_redirects=True)
    assert message in response.data.decode()
    assert count_rows("products") == before


# ---------- CSV upload ----------

def upload(client, content, filename="reviews.csv"):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return client.post("/reviews/upload", content_type="multipart/form-data", follow_redirects=True,
                       data={"file": (io.BytesIO(content), filename)})


def test_upload_adds_reviews_with_their_analysis(analyst):
    response = upload(analyst, f"product,rating,review,customer,date\n"
                               f"{PRODUCT},5,excellent product,Asha,2026-01-31\n"
                               f"{PRODUCT.lower()},1,terrible awful battery,,\n")

    assert b"Added 2 reviews from reviews.csv" in response.data
    newest, oldest = models.search_reviews()
    assert oldest["review_date"] == datetime(2026, 1, 31)
    assert oldest["customer_name"] == "Asha"
    assert oldest["sentiment"] == "Positive"
    assert oldest["source"] == "csv"
    assert oldest["submitted_by"] == analyst_id()
    assert newest["customer_name"] is None
    assert newest["sentiment"] == "Negative"
    assert models.get_review(newest["id"])["aspects"][0]["aspect"] == "Battery"


@pytest.mark.parametrize("header", ["Product,Rating,Review", "product_name,rating,review_text",
                                    "Product Name, Rating , Review Text", "rating,review,product,ignored"])
def test_upload_accepts_different_column_names(admin, header):
    names = [name.strip().lower() for name in header.split(",")]
    cells = {"rating": "5", "review": "nice", "review_text": "nice", "product": PRODUCT,
             "product_name": PRODUCT, "product name": PRODUCT, "review text": "nice", "ignored": "x"}
    upload(admin, header + "\n" + ",".join(cells[name] for name in names) + "\n")
    assert count_rows("reviews") == 1


def test_upload_accepts_its_own_export(admin):
    add_review(text="excellent product", customer_name="Asha")
    exported = admin.get("/reviews/export").data
    upload(admin, exported)
    assert count_rows("reviews") == 2


@pytest.mark.parametrize("content", [
    f"product,rating,review\n{PRODUCT},5,\"camera 😍, தமிழ், हिन्दी\"\n".encode("utf-8"),
    f"﻿product,rating,review\n{PRODUCT},5,\"camera 😍, தமிழ், हिन्दी\"\n".encode("utf-8"),
])
def test_upload_keeps_emoji_and_other_languages(admin, content):
    upload(admin, content)
    assert models.search_reviews()[0]["review_text"] == "camera 😍, தமிழ், हिन्दी"


def test_upload_reads_excel_windows_encoding(admin):
    upload(admin, f"product,rating,review\n{PRODUCT},5,café\n".encode("cp1252"))
    assert models.search_reviews()[0]["review_text"] == "café"


def test_upload_accepts_ratings_like_5_point_0_and_multiline_text(admin):
    upload(admin, f'product,rating,review\n{PRODUCT},5.0,"line one\nline two"\n')
    review = models.search_reviews()[0]
    assert review["rating"] == 5
    assert review["review_text"] == "line one\nline two"


def test_upload_skips_blank_rows_and_handles_extra_or_missing_cells(admin):
    upload(admin, f"product,rating,review\n,,\n\n{PRODUCT},5,nice,extra,cells\n")
    assert count_rows("reviews") == 1


@pytest.mark.parametrize("row, message", [
    ("Not A Product,5,nice", 'Unknown product'),
    (",5,nice", "Unknown product"),
    (f"{PRODUCT},9,nice", "rating from 1 to 5"),
    (f"{PRODUCT},0,nice", "rating from 1 to 5"),
    (f"{PRODUCT},4.5,nice", "rating from 1 to 5"),
    (f"{PRODUCT},abc,nice", "rating from 1 to 5"),
    (f"{PRODUCT},nan,nice", "rating from 1 to 5"),
    (f"{PRODUCT},,nice", "rating from 1 to 5"),
    (f"{PRODUCT},5,", "enter the review text"),
    (f"{PRODUCT},5", "enter the review text"),
    (f"{PRODUCT},5," + "x" * 5001, "at most 5000 characters"),
    (f"{PRODUCT},5,nice,{'x' * 101}", "at most 100 characters"),
    (f"{PRODUCT},5,nice,Asha,31/01/2026", "2026-01-31"),
    (f"{PRODUCT},5,nice,Asha,1999-01-01", "before 2000"),
    (f"{PRODUCT},5,nice,Asha,{(datetime.now() + timedelta(days=2)).date()}", "in the future"),
])
def test_one_bad_row_means_nothing_is_added(admin, row, message):
    content = f"product,rating,review,customer,date\n{PRODUCT},5,good row\n{row}\n"
    page = upload(admin, content).data.decode()
    assert "Nothing was added" in page
    assert "Row 3:" in page
    assert message in page
    assert count_rows("reviews") == 0


@pytest.mark.parametrize("content, filename, message", [
    ("", "reviews.csv", "needs these columns"),
    ("product,rating\nx,5\n", "reviews.csv", "needs these columns: review"),
    ("product,rating,review\n", "reviews.csv", "no reviews"),
    ("product,rating,review\nx,5,y\n", "reviews.txt", "Only .csv"),
    ("product,rating,review\nx,5,y\n", "reviews.csv.exe", "Only .csv"),
    (b"\xff\xfep\x00r\x00o\x00", "reviews.csv", "needs these columns"),
])
def test_unusable_files_are_rejected(admin, content, filename, message):
    page = upload(admin, content, filename).data.decode()
    assert message in page
    assert count_rows("reviews") == 0


def test_upload_without_a_file(admin):
    response = admin.post("/reviews/upload", data={}, follow_redirects=True)
    assert b"choose a CSV file" in response.data


def test_upload_row_limit(admin):
    rows = f"{PRODUCT},5,nice\n" * 5001
    page = upload(admin, "product,rating,review\n" + rows).data.decode()
    assert "at most 5000 reviews" in page
    assert count_rows("reviews") == 0


def test_upload_size_limit(admin):
    response = upload(admin, "x" * (5 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert b"too large" in response.data


def test_many_upload_errors_are_shortened(admin):
    page = upload(admin, "product,rating,review\n" + "Nope,5,nice\n" * 25).data.decode()
    assert "And 5 more." in page


def test_same_file_cannot_be_uploaded_twice(admin):
    content = f"product,rating,review\n{PRODUCT},5,nice\n"
    upload(admin, content)
    page = upload(admin, content, "renamed.csv").data.decode()
    assert "already been uploaded" in page
    assert count_rows("reviews") == 1


def test_a_rejected_file_can_be_fixed_and_uploaded_again(admin):
    assert b"Nothing was added" in upload(admin, f"product,rating,review\n{PRODUCT},9,nice\n").data
    upload(admin, f"product,rating,review\n{PRODUCT},5,nice\n")
    assert count_rows("reviews") == 1


def test_uploaded_file_is_kept_under_a_safe_name(admin):
    upload(admin, f"product,rating,review\n{PRODUCT},5,nice\n", "../../evil.csv")
    saved = os.listdir(flask_app.app.config["UPLOAD_FOLDER"])
    assert len(saved) == 1
    assert saved[0].endswith(".csv") and len(saved[0]) == 68


def test_uploaded_text_is_escaped_on_the_page(admin):
    upload(admin, f'product,rating,review,customer\n{PRODUCT},5,<script>alert(1)</script>,<b>x</b>\n')
    page = admin.get("/reviews").data.decode()
    assert "<script>alert(1)</script>" not in page
    assert "<b>x</b>" not in page


def test_uploaded_formula_is_made_safe_on_export(admin):
    upload(admin, f"product,rating,review\n{PRODUCT},5,=1+1\n")
    assert b"'=1+1" in admin.get("/reviews/export").data


# ---------- Friendly error pages ----------

def test_error_pages(admin, analyst):
    assert b"Page not found" in admin.get("/nothing-here").data
    assert b"have access" in analyst.post("/products", data={"name": "x"}).data
