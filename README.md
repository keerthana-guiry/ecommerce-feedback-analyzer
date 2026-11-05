# Ecommerce Feedback Analyzer

*Originally built at a hackathon with team SheCodes — rebuilt and expanded independently
into a customer intelligence platform.*

A web application where business users add customer reviews and see the sentiment,
product aspects, and trends found in them.

This project is being built in phases. Pages mark anything that isn't built yet with the
phase it arrives in.

| Phase | Work | Status |
| --- | --- | --- |
| 1 | Dashboard UI | Done |
| 2 | Backend and MySQL database | Done |
| 3 | User roles, CSV upload, review management | Done |
| 4 | Sentiment analysis with VADER | Done |
| 5 | Aspect-based sentiment analysis | Not started |
| 6 | Complaint detection and product insights | Not started |
| 7 | Recommendations and reports | Not started |
| 8 | Final testing and deployment | Not started |

## Features

- Dashboard with key metrics, sentiment distribution, review trend, top complaint keywords, top products, and recent reviews
- Review Analysis to submit a review and see its sentiment, confidence, and aspects
- CSV upload that checks every row and adds nothing if any row has a problem
- All Reviews with search, filters, date sorting, editing, deleting, and CSV export
- Product Insights comparing sentiment, ratings, and health status across products
- Reports & Trends with daily, weekly, and monthly sentiment and satisfaction charts
- Settings for your username, password, and default dashboard time period

**Roles**

| | Analyst | Admin |
| --- | --- | --- |
| View all pages and export reviews | Yes | Yes |
| Add reviews and upload CSV files | Yes | Yes |
| Edit and delete reviews | Only ones they submitted | Any review |
| Add products | No | Yes |
| Create and delete accounts, reset passwords | No | Yes |

**CSV Upload Format**

The columns `product`, `rating`, and `review` are required. `customer` and `date` (like `2026-01-31`)
are optional. Products must already exist in the app. Files can have up to 5,000 reviews or 5 MB.
```
product,rating,review,customer,date
Laptop Backpack,5,Strong zips and very comfortable,Asha,2026-01-31
```

**Sentiment Engine**
- [VADER](https://github.com/cjhutto/vaderSentiment), a published dictionary-and-rules method, handles negation, intensifiers, "but", and emoji
- Added on top of VADER:
  - Common product-review words its dictionary is missing, like "flimsy" and "overpriced"
  - Mixed sentiment, found by scoring each part of a review separately, or when the words and stars strongly disagree
  - The star rating as a supporting signal (70% text, 30% rating)
- Each result records which engine produced it, and admins can re-analyze older results from Settings
- Results are never labelled fake. Suspicious reviews are only flagged for a person to check.

**Known Limits of the Sentiment Engine**
- Confidence shows how strong and consistent the signals are. It isn't a measured chance of being correct, because VADER doesn't produce a probability.
- No accuracy figure is claimed, because the engine hasn't been measured on a real labelled dataset yet. `tests/labelled_reviews.py` is a small hand-written sanity check, not a measure of accuracy.
- Dictionary methods miss sarcasm and indirect wording, like "Oh great, another one that broke".
- Only English text is analyzed. Tamil and Hindi are detected, and those reviews use only the star rating and say so. Other languages written in Latin letters aren't detected and usually score as Neutral.

**Security**
- Hashed passwords and CSRF protection on every form
- Permissions are checked on the server for every action
- Changing a password or deleting an account logs it out everywhere
- Parameterized SQL for every query
- The app connects to MySQL with a limited account, not root
- Passwords and keys live in a private `.env` file that Git ignores

## Tech Stack
- Python, Flask
- MySQL
- VADER (sentiment analysis)
- Chart.js
- HTML/CSS/JavaScript (custom, no framework)
- pytest

## Database
Original reviews are stored separately from the analysis, so reviews can be analyzed again
later without changing them.

| Table | Holds |
| --- | --- |
| `users` | Admin and analyst accounts |
| `products` | Products that reviews belong to |
| `reviews` | The original review, rating, and customer name |
| `sentiment_results` | One analysis for each review |
| `aspect_results` | The sentiment of each product aspect in a review |
| `recommendations` | Business recommendations (from Phase 7) |

## Project Structure
```
├── ecommerce-feedback/
│   ├── app.py              # Creates the Flask app
│   ├── setup_database.py   # Creates the databases and the .env file
│   ├── seed_demo.py        # Optional sample data for demos
│   ├── routes/             # One file of pages for each part of the app
│   ├── db/
│   │   ├── config.py       # MySQL connection settings
│   │   ├── models.py       # All SQL queries
│   │   └── schema.sql      # Table definitions
│   ├── nlp/                # Text analysis
│   ├── utils/              # Permissions, input checks, CSV import and export
│   ├── static/             # CSS and Chart.js scripts
│   ├── templates/          # Page templates
│   ├── uploads/            # Uploaded CSV datasets (not tracked by Git)
│   └── reports/            # Generated reports (not tracked by Git)
├── tests/                  # Automated tests
├── .env.example            # The settings the app expects
├── requirements.txt
└── README.md
```

## How to Run Locally
You need Python and a running MySQL server.

1. Clone this repository
2. Install the dependencies: `pip install -r requirements.txt`
3. Set up the database: `python ecommerce-feedback/setup_database.py`
4. Run the app: `python ecommerce-feedback/app.py`
5. Open `http://127.0.0.1:5000`

Step 3 asks for your MySQL root password, which it doesn't save. It creates the databases,
a limited MySQL account for the app, the `.env` file, and an `admin` login. The admin password
prints once, so save it. To choose your own, set `ADMIN_PASSWORD` before running step 3.

After pulling a newer version of the app, run step 3 again. It keeps your data and adds anything new.

### Demo Data
To fill the dashboard with sample reviews, run this once after step 3:
```
python ecommerce-feedback/seed_demo.py
```
Use it on a local database only.

### Optional Settings
Add these to `.env`:

| Variable | What it does |
| --- | --- |
| `FLASK_DEBUG` | Set to `1` to turn on debug mode for local development only |

## Running the Tests
The tests use the separate `ecommerce_feedback_test` database, so they never touch your real data.
MySQL must be running and step 3 above must be done first.
```
python -m pytest
```

## Example
A review with a 1-star rating says: *"Absolutely terrible, broke after one day."*
The app stores it, detects **Negative** with its confidence, and adds it to the dashboard charts.
