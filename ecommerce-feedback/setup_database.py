"""
One-time MySQL setup. Run it once from the project folder:

    python ecommerce-feedback/setup_database.py

It asks for your MySQL root password (which is not saved), then creates:
  - the app database, plus a separate one for automated tests
  - a limited `feedback_app` MySQL account that can only use those databases
  - a private .env file with that account's random password
  - the tables, sample products, and an admin account

Safe to run again: existing data and settings are kept.
"""

import getpass
import os
import secrets
import sys

import mysql.connector
from dotenv import dotenv_values, set_key
from werkzeug.security import generate_password_hash

from db.config import ENV_FILE, apply_schema

APP_USER = "feedback_app"
APP_DATABASE = "ecommerce_feedback"
TEST_DATABASE = "ecommerce_feedback_test"

# Starting products, until products can be added in the app
SAMPLE_PRODUCTS = [
    "Wireless Bluetooth Earbuds",
    "Smart Fitness Watch",
    "Stainless Steel Water Bottle",
    "Ergonomic Office Chair",
    "Portable Power Bank 20000mAh",
    "Laptop Backpack",
]


def read_or_create_settings():
    """Keep whatever .env already has and fill in anything missing."""
    settings = dotenv_values(ENV_FILE) if os.path.exists(ENV_FILE) else {}
    defaults = {
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "DB_USER": APP_USER,
        # The suffix satisfies MySQL's optional password strength rules
        "DB_PASSWORD": secrets.token_urlsafe(24) + "-Aa1",
        "DB_NAME": APP_DATABASE,
        "SECRET_KEY": secrets.token_hex(32),
    }
    for key, value in defaults.items():
        if not settings.get(key):
            set_key(ENV_FILE, key, value, quote_mode="never")
            settings[key] = value
    return settings


def create_databases_and_account(root_connection, settings):
    cursor = root_connection.cursor()
    account = f"'{APP_USER}'@'localhost'"

    cursor.execute(f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s", (settings["DB_PASSWORD"],))
    cursor.execute(f"ALTER USER {account} IDENTIFIED BY %s", (settings["DB_PASSWORD"],))

    for database in (settings["DB_NAME"], TEST_DATABASE):
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4")
        cursor.execute(f"GRANT ALL PRIVILEGES ON `{database}`.* TO {account}")

    cursor.execute("FLUSH PRIVILEGES")
    cursor.close()


def add_starting_data(connection):
    """Add the sample products and an admin account, if they don't exist yet."""
    cursor = connection.cursor()
    cursor.executemany("INSERT IGNORE INTO products (name) VALUES (%s)",
                       [(name,) for name in SAMPLE_PRODUCTS])

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admin_password = None
    if cursor.fetchone()[0] == 0:
        admin_password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ('admin', %s, 'admin')",
            (generate_password_hash(admin_password),)
        )
    connection.commit()
    cursor.close()
    return admin_password


def main():
    settings = read_or_create_settings()
    host, port = settings["DB_HOST"], int(settings["DB_PORT"])

    root_password = getpass.getpass("MySQL root password (hidden as you type): ")
    try:
        root_connection = mysql.connector.connect(host=host, port=port, user="root", password=root_password)
    except mysql.connector.Error as error:
        sys.exit(f"Could not connect to MySQL as root: {error.msg}")

    create_databases_and_account(root_connection, settings)
    root_connection.close()

    admin_password = None
    for database in (settings["DB_NAME"], TEST_DATABASE):
        connection = mysql.connector.connect(host=host, port=port, user=settings["DB_USER"],
                                             password=settings["DB_PASSWORD"], database=database)
        apply_schema(connection)
        if database == settings["DB_NAME"]:
            admin_password = add_starting_data(connection)
        connection.close()

    print(f"MySQL setup complete. Database: {settings['DB_NAME']}. Settings saved to .env.")
    if admin_password:
        print(f"Created admin account. Username: admin, password: {admin_password}")
        print("Save this password. It is only shown once.")
    else:
        print("Your existing admin account was kept.")


if __name__ == "__main__":
    main()
