"""Input checks shared by the routes. Each returns an error message, or None if valid."""

import re

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{3,50}")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_REVIEW_LENGTH = 5000
MAX_CUSTOMER_NAME_LENGTH = 100
MAX_PRODUCT_NAME_LENGTH = 150


def username_error(username):
    if not USERNAME_PATTERN.fullmatch(username):
        return "Usernames need 3 to 50 letters, numbers, dots, dashes or underscores."
    return None


def password_error(password):
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return f"Passwords need {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters."
    return None


def review_error(rating, review_text, customer_name):
    if rating not in range(1, 6):
        return "Please give a rating from 1 to 5."
    if not review_text:
        return "Please enter the review text."
    if len(review_text) > MAX_REVIEW_LENGTH:
        return f"Review text can be at most {MAX_REVIEW_LENGTH} characters."
    if len(customer_name) > MAX_CUSTOMER_NAME_LENGTH:
        return f"Customer name can be at most {MAX_CUSTOMER_NAME_LENGTH} characters."
    return None


def product_name_error(name):
    if not name:
        return "Please enter a product name."
    if len(name) > MAX_PRODUCT_NAME_LENGTH:
        return f"Product names can be at most {MAX_PRODUCT_NAME_LENGTH} characters."
    return None
