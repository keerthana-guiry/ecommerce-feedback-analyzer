"""
Ecommerce Feedback Analyzer - creates the Flask app and connects its parts.
Pages live in routes/, MySQL queries in db/, and text analysis in nlp/.

Run `python ecommerce-feedback/setup_database.py` once before the first start.
"""

import os
import secrets

import mysql.connector
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

import db.config  # loads the .env file
from routes import ALL_BLUEPRINTS


def create_app():
    app = Flask(__name__)
    # Without SECRET_KEY set, a random key means everyone is logged out on restart
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    CSRFProtect(app)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.errorhandler(mysql.connector.Error)
    def database_unavailable(error):
        app.logger.error("Database error: %s", error)
        return render_template("database_error.html"), 503

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
