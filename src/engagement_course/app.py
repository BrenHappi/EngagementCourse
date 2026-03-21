import secrets
from os import getenv
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from engagement_course.auth import auth_bp
from engagement_course.routes import main_bp
from engagement_course.admin import admin_bp
from engagement_course.database import DatabaseRepository
from engagement_course.ffc_parser import FFCParser
import engagement_course.config as config

load_dotenv()
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

    db.replace_races(races)
    return len(races)

def create_app() -> Flask:
    app = Flask(__name__, static_folder="assets")
    app.secret_key = config.SECRET_KEY
    csrf.init_app(app)
    db = DatabaseRepository()
    app.config["repository"] = db
    app.config['registration_token'] = config.REGISTRATION_TOKEN

    try:
        seeded_count = seed_races_from_ffc(db)
        if seeded_count:
            app.logger.info("Seeded %s races from FFC", seeded_count)
    except Exception:
        app.logger.exception("FFC seed failed at startup")

    if db.get_user_by_id(1) is None:
        db.create_user(
            firstname="admin",
            lastname="admin",
            email=config.ADMIN_EMAIL,
            username="admin",
            password=config.ADMIN_PASSWORD,
            role="admin",
        )

    lm.init_app(app)
    lm.login_view = "auth.login"

    @lm.user_loader
    def load_user(user_id: str):
        return db.get_user_by_id(int(user_id))

    @app.cli.command("seed-races")
    def seed_races_command() -> None:
        """Fetch races from all configured FFC departments and replace DB races."""
        seeded_count = seed_races_from_ffc(db, force=True)
        print(f"Seeded {seeded_count} races from FFC")

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # TMP: display registration token:
    print(f"Registration URL: {app.config['registration_token']}")

    return app