from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.products import products_bp
from routes.reports import reports_bp
from routes.reviews import reviews_bp
from routes.settings import settings_bp

ALL_BLUEPRINTS = (auth_bp, dashboard_bp, reviews_bp, products_bp, reports_bp, settings_bp)
