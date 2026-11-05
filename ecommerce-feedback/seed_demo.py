"""
Fills a local database with sample reviews so the dashboard has something to
show. For demos only. Run setup_database.py first, then run this once:

    python ecommerce-feedback/seed_demo.py
"""

import random
from datetime import datetime, timedelta

from db import models
from nlp.sentiment import analyze_sentiment

DEMO_CUSTOMERS = ["Asha", "Ravi", "Meera", "John", "Fatima", "Wei", "Carlos", "Nina"]

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
    if models.count_reviews() > 0:
        print("This database already has reviews, so no demo data was added.")
        return

    rng = random.Random(7)
    product_ids = [product["id"] for product in models.get_all_products()]
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
            models.add_review(
                product_ids[index], rating, text, analyze_sentiment(text, rating),
                customer_name=rng.choice(DEMO_CUSTOMERS),
                review_date=now - timedelta(days=days_ago, minutes=rng.randint(0, 600))
            )
            created += 1

    print(f"Added {created} demo reviews.")


if __name__ == "__main__":
    seed()
