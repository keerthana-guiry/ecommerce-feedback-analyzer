"""
Fills a local database with sample customers and reviews so the admin
dashboard has something to show. For demos only - run it once with:

    python ecommerce-feedback/seed_demo.py
"""

import random
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import database as db
from sentiment import analyze_sentiment

DEMO_CUSTOMERS = ["asha", "ravi", "meera", "john", "fatima", "wei", "carlos", "nina"]

# (rating, review text)
REVIEWS = [
    (5, "Absolutely amazing, works perfectly and feels very durable!"),
    (5, "Excellent quality and really comfortable. I would recommend it."),
    (5, "Fantastic value, delivery was fast and it is so reliable."),
    (4, "Very good product, easy to use and worth the price."),
    (4, "Great build, happy with it after a month of use."),
    (4, "Nice design and smooth performance, pleased overall."),
    (3, "It is okay, does the job."),
    (3, "Average product, nothing special to report."),
    (3, "Great comfort but terrible packaging."),
    (3, "Excellent battery but the strap is flimsy and disappointing."),
    (2, "Somewhat disappointing quality, feels a bit flimsy."),
    (2, "Delivery was delayed and the box arrived damaged."),
    (1, "Terrible, broke after one day. Complete waste of money."),
    (1, "Defective item and the support team was rude."),
    (5, "GOOD GOOD GOOD GOOD PRODUCT!!!!!!"),
]

GOOD_WEIGHTS = [6, 6, 6, 5, 5, 4, 1, 1, 2, 2, 1, 1, 1, 1, 1]
POOR_WEIGHTS = [1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 6, 6, 7, 6, 1]

# How likely each product is to get a good review, so products score differently
PRODUCT_QUALITY = [0.95, 0.9, 0.7, 0.55, 0.3, 0.1]

HISTORY_DAYS = 90


def seed():
    db.init_db()
    if db.get_user_by_username(DEMO_CUSTOMERS[0]):
        print("Demo data already exists, nothing to do.")
        return

    for name in DEMO_CUSTOMERS:
        # Demo customers exist only to own reviews, so nobody needs their password
        db.create_user(name, generate_password_hash(secrets.token_urlsafe(16)))

    rng = random.Random(7)
    user_ids = [db.get_user_by_username(name)["id"] for name in DEMO_CUSTOMERS]
    product_ids = [p["id"] for p in db.get_all_products()]
    now = datetime.now()
    created = 0

    for days_ago in range(HISTORY_DAYS - 1, -1, -1):
        # Review volume grows steadily across the history
        progress = (HISTORY_DAYS - days_ago) / HISTORY_DAYS
        daily_reviews = round(2 + progress * 10) + rng.randint(-1, 1)
        for _ in range(daily_reviews):
            index = rng.randrange(len(product_ids))
            # Reviews improve slightly over time, so the charts show a trend
            is_good = rng.random() < PRODUCT_QUALITY[index] + progress * 0.1 - 0.05
            weights = GOOD_WEIGHTS if is_good else POOR_WEIGHTS
            rating, text = rng.choices(REVIEWS, weights=weights)[0]
            result = analyze_sentiment(text, rating)
            when = now - timedelta(days=days_ago, minutes=rng.randint(0, 600))
            db.add_feedback(
                rng.choice(user_ids), product_ids[index], rating, text,
                result["sentiment"], result["score"], result["confidence"],
                result["emotion"], result["spam_score"],
                created_at=when.strftime("%Y-%m-%d %H:%M")
            )
            created += 1

    print(f"Added {len(DEMO_CUSTOMERS)} demo customers and {created} reviews.")


if __name__ == "__main__":
    seed()
