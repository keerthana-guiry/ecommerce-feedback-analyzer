# Smart Feedback Analyzer — E-Commerce Edition

*Originally built at a hackathon with team SheCodes — rebuilt and expanded independently
into a full-featured feedback management system.*

A web application where customers can leave feedback on purchased products, and admins
can monitor sentiment trends across all feedback using visual analytics.

## Features

**Customer Side**
- Register and log in securely (hashed passwords)
- Select a product and leave a rating (1-5 stars) + written feedback
- Automatic sentiment and emotion detection on submission
- View, edit, and delete your own feedback

**Admin Side**
- Dashboard with key metrics, sentiment distribution, review trend, top complaint keywords, top products, and recent reviews
- Review Analysis to submit a review and see its sentiment, confidence, and aspects
- All Reviews with search, product, sentiment, and rating filters, date sorting, and CSV export
- Product Insights comparing sentiment, ratings, and health status across products
- Reports & Trends with daily, weekly, and monthly sentiment and satisfaction charts

**Sentiment Engine**
- Custom rule-based analyzer (not a black-box library) that considers:
  - Intensifiers ("very good" scores higher than "good")
  - Downtoners ("somewhat bad" scores lower in magnitude)
  - Negation handling ("not good" flips polarity correctly)
  - Contrast words ("good but slow" weights the part after "but" more)
  - Punctuation emphasis (exclamation marks boost confidence)
  - Star rating blended in as a supporting signal for higher accuracy

**Security**
- CSRF protection on every form
- Secret key and admin password are never stored in the code

## Tech Stack
- Python, Flask
- SQLite (file-based database, zero setup)
- Chart.js (for admin analytics)
- HTML/CSS (custom, no framework)
- pytest (for tests)

## Project Structure
```
├── ecommerce-feedback/
│   ├── app.py              # Main Flask app & routes
│   ├── sentiment.py        # Sentiment analysis engine
│   ├── database.py         # SQLite setup & queries
│   ├── seed_demo.py        # Optional sample data for demos
│   ├── static/
│   │   ├── css/style.css   # Deep Forest + Emerald design
│   │   └── js/             # Chart.js charts for each page
│   ├── templates/          # Page templates
│   ├── routes/             # Backend routes (from Phase 2)
│   ├── db/                 # MySQL config and models (from Phase 2)
│   ├── nlp/                # Sentiment and aspect analysis (from Phase 4)
│   ├── utils/              # Shared helpers
│   ├── uploads/            # Uploaded CSV datasets (not tracked by Git)
│   └── reports/            # Generated reports (not tracked by Git)
├── tests/                  # Automated tests
├── requirements.txt
└── README.md
```

## How to Run Locally
1. Clone this repository
2. Install the dependencies: `pip install -r requirements.txt`
3. Run the app: `python ecommerce-feedback/app.py`
4. Open `http://127.0.0.1:5000`

The first run creates an `admin` account and prints its random password in the terminal.
Save it, because it's only shown once. Customers can register from the login page.

### Demo Data
To fill the dashboard with sample customers and reviews, run this before starting the app:
```
python ecommerce-feedback/seed_demo.py
```
If this is the first run, the admin password prints here instead. Use it on a local database
only, and delete `ecommerce-feedback/feedback.db` to start fresh.

### Optional Settings
Set these as environment variables before running the app:

| Variable | What it does |
| --- | --- |
| `ADMIN_PASSWORD` | Uses this password for the admin account when it's first created |
| `SECRET_KEY` | Keeps users logged in across restarts (otherwise a random key is used) |
| `FLASK_DEBUG` | Set to `1` to turn on debug mode for local development only |
| `FEEDBACK_DB` | Path to the database file (defaults to `ecommerce-feedback/feedback.db`) |

## Running the Tests
```
python -m pytest
```

## Example
A customer submits: *"Absolutely terrible, broke after one day."* with a 1-star rating.
The system detects: **Negative** (high confidence), and it appears on the admin
dashboard's sentiment chart.
