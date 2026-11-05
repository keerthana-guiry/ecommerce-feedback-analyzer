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
| 3 | User roles, CSV upload, review management | Not started |
| 4 | Sentiment analysis with VADER | Not started |
| 5 | Aspect-based sentiment analysis | Not started |
| 6 | Complaint detection and product insights | Not started |
| 7 | Recommendations and reports | Not started |
| 8 | Final testing and deployment | Not started |

## Features

- Dashboard with key metrics, sentiment distribution, review trend, top complaint keywords, top products, and recent reviews
- Review Analysis to submit a review and see its sentiment, confidence, and aspects
- All Reviews with search, product, sentiment, and rating filters, date sorting, and CSV export
- Product Insights comparing sentiment, ratings, and health status across products
- Reports & Trends with daily, weekly, and monthly sentiment and satisfaction charts

**Sentiment Engine**
- Custom rule-based analyzer for now. VADER replaces it in Phase 4. It considers:
  - Intensifiers ("very good" scores higher than "good")
  - Downtoners ("somewhat bad" scores lower in magnitude)
  - Negation handling ("not good" flips polarity correctly)
  - Contrast words ("good but slow" weights the part after "but" more)
  - Punctuation emphasis (exclamation marks boost confidence)
  - Star rating blended in as a supporting signal
- Results are never labelled fake. Suspicious reviews are only flagged for a person to check.

**Security**
- Hashed passwords and CSRF protection on every form
- Parameterized SQL for every query
- The app connects to MySQL with a limited account, not root
- Passwords and keys live in a private `.env` file that Git ignores

## Tech Stack
- Python, Flask
- MySQL
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
│   ├── utils/              # Login check and safe CSV export
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
