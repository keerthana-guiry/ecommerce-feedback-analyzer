# Smart Feedback Analyzer — E-Commerce Edition

*Originally built at a hackathon with team SheCodes — rebuilt and expanded independently
into a full-featured feedback management system.*

A web application where customers can leave feedback on purchased products, and admins
can monitor sentiment trends across all feedback using visual analytics.

## Features

**Customer Side**
- Register and log in securely (hashed passwords)
- Select a purchased product and leave a rating (1-5 stars) + written feedback
- Automatic sentiment detection on submission
- View personal feedback history

**Admin Side**
- Secure admin login
- View all customer feedback across all products
- Real-time sentiment breakdown chart (Positive / Negative / Neutral)
- Summary stats (total feedback, sentiment counts, confidence scores)

**Sentiment Engine**
- Custom rule-based analyzer (not a black-box library) that considers:
  - Intensifiers ("very good" scores higher than "good")
  - Downtoners ("somewhat bad" scores lower in magnitude)
  - Negation handling ("not good" flips polarity correctly)
  - Punctuation emphasis (exclamation marks boost confidence)
  - Star rating blended in as a supporting signal for higher accuracy

## Tech Stack
- Python, Flask
- SQLite (file-based database, zero setup)
- Chart.js (for admin analytics)
- HTML/CSS (custom, no framework)

## Project Structure
```
ecommerce-feedback/
├── app.py                 # Main Flask app & routes
├── sentiment.py            # Sentiment analysis engine
├── database.py              # SQLite setup & queries
├── static/
│   └── style.css
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── customer_dashboard.html
│   └── admin_dashboard.html
└── README.md
```

## How to Run Locally
1. Clone this repository
2. Install Flask: `pip install flask`
3. Run the app: `python app.py`
4. Open `http://127.0.0.1:5000`

**Default admin login:** username `admin`, password `admin123`

Customers can register their own account from the login page.

## Example
A customer submits: *"Absolutely terrible, broke after one day."* with a 1-star rating.
The system detects: **Negative** (high confidence), and it appears instantly on the
admin dashboard's sentiment chart.
