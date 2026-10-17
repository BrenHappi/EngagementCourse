from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

from engagement_course.auth import auth_bp
from engagement_course.calendar import calendar_bp
from engagement_course.admin import admin_bp
from engagement_course.api import api_bp
from engagement_course.profile import profile_bp
from engagement_course.database import DatabaseRepository
from engagement_course.ffc_parser import FFCParser
from engagement_course.models import Category, CATEGORIES, EngagementStatus
from engagement_course.recap import send_due_recaps
import engagement_course.config as config

lm = LoginManager()
csrf = CSRFProtect()


def seed_races_from_ffc(db: DatabaseRepository, force: bool = False) -> int:
    if not force and db.list_races():
        return 0

    races = []
    for department in config.FFC_CALENDAR_URLS:
        parser = FFCParser(department=department)
        html = parser.fetch_calendar()
        races.extend(parser.parse_calendar(html))

    if not races:
        # Site down or page layout changed: keep the calendar rather than emptying it
        raise RuntimeError("No race parsed from the FFC calendar, races left unchanged")
    db.replace_races(races)
    return len(races)

def create_app() -> Flask:
    config.validate()
    app = Flask(__name__, static_folder="assets")
    app.logger.setLevel(config.LOG_LEVEL)
    app.secret_key = config.SECRET_KEY
    # Behind Caddy: trust its X-Forwarded-* headers (client IP, https scheme, host)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    https = config.EXTERNAL_URL.startswith("https://")
    app.config.update(
        SESSION_COOKIE_SECURE=https,
        REMEMBER_COOKIE_SECURE=https,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SAMESITE="Lax",
    )
    csrf.init_app(app)
    db = DatabaseRepository()
    app.config["repository"] = db
    app.config["external_url"] = config.EXTERNAL_URL

    # SMTP configuration
    app.config['notify'] = config.notify
    if app.config['notify']:
        app.config['smtp_hostname'] = config.SMTP_HOSTNAME
        app.config['smtp_port'] = config.SMTP_PORT
        app.config['smtp_username'] = config.SMTP_USERNAME
        app.config['smtp_password'] = config.SMTP_PASSWORD
    else:
        app.logger.warning("SMTP not configured: email notifications are disabled")

    try:
        seeded_count = seed_races_from_ffc(db)
        if seeded_count:
            app.logger.info("Seeded %s races from FFC", seeded_count)
    except Exception:
        app.logger.exception("FFC seed failed at startup")

    if db.get_user_by_id(1) is None:
        if not (config.ADMIN_EMAIL and config.ADMIN_PASSWORD):
            raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD are required to create the initial admin account")
        db.create_user(
            firstname="admin",
            lastname="admin",
            email=config.ADMIN_EMAIL,
            username="admin",
            password=config.ADMIN_PASSWORD,
            role="admin",
            managed_categories=[
                Category(level, number)
                for level, numbers in CATEGORIES.items()
                for number in numbers
            ],
            address=None,
        )

    lm.init_app(app)
    lm.login_view = "auth.login"
    lm.login_message = "Connectez-vous pour accéder à cette page"
    lm.login_message_category = "info"

    @lm.user_loader
    def load_user(user_id: str):
        return db.get_user_by_id(int(user_id))

    @app.cli.command("seed-races")
    def seed_races_command() -> None:
        """Fetch races from all configured FFC departments and replace DB races."""
        seeded_count = seed_races_from_ffc(db, force=True)
        print(f"Seeded {seeded_count} races from FFC")

    @app.cli.command("send-admin-recaps")
    def send_admin_recaps_command() -> None:
        """Email admins whose weekly recap is due (meant to run every hour from cron)."""
        if not app.config['notify']:
            print("SMTP not configured: no recap sent")
            return
        sent_count = send_due_recaps(db, datetime.now(ZoneInfo(config.TIMEZONE)), config.EXTERNAL_URL)
        print(f"Sent {sent_count} admin recap(s)")

    @app.context_processor
    def inject_pending_count():
        # Badge of the "Validation" menu entry: requests waiting in the admin's categories
        if not current_user.is_authenticated or current_user.role != "admin":
            return {}
        categories = current_user.managed_categories or []
        return {"pending_count": len(db.list_engagements(status=EngagementStatus.PENDING.value, categories=categories))}

    @app.get("/health")
    def health():
        if not db.ping():
            return jsonify({"status": "error", "database": "unavailable"}), 503
        return jsonify({"status": "ok"}), 200

    app.register_blueprint(auth_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(profile_bp)

    return app