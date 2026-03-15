import secrets
from os import getenv
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager

from engagement_course.auth import auth_bp
from engagement_course.routes import main_bp
from engagement_course.database import DatabaseRepository
import engagement_course.config

load_dotenv()
lm = LoginManager()

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    db = DatabaseRepository()
    app.config["repository"] = db
    app.config['registration_token'] = engagement_course.config.REGISTRATION_TOKEN

    if db.get_user_by_id(1) is None:
        db.create_user("admin", getenv("ADMIN_EMAIL"), getenv("ADMIN_PASSWORD"), role="admin")

    lm.init_app(app)
    lm.login_view = "auth.login"

    @lm.user_loader
    def load_user(user_id: str):
        return db.get_user_by_id(int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # TMP: display registration token:
    print(f"Registration token: {app.config['registration_token']}")

    return app