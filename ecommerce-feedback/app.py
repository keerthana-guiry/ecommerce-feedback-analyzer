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

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def error_page(status, heading, message):
    return render_template("error.html", heading=heading, message=message), status


def create_app():
    app = Flask(__name__)
    # Without SECRET_KEY set, a random key means everyone is logged out on restart
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
    CSRFProtect(app)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.errorhandler(403)
    def forbidden(error):
        return error_page(403, "You don't have access to this",
                          "Ask an admin if you need this changed.")

    @app.errorhandler(404)
    def not_found(error):
        return error_page(404, "Page not found", "This page doesn't exist or has been removed.")

    @app.errorhandler(413)
    def too_large(error):
        return error_page(413, "That file is too large",
                          f"Files can be at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")

    @app.errorhandler(mysql.connector.Error)
    def database_unavailable(error):
        app.logger.error("Database error: %s", error)
        return error_page(503, "Can't reach the database",
                          "Please check that MySQL is running, then try again. "
                          "If this is the first run, or you just updated the app, run setup_database.py.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
