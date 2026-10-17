import datetime

import pytest

import engagement_course.app as app_module
from engagement_course import config
from engagement_course.models import Category, RaceEvent

ADMIN_PASSWORD = "admin-pw"
USER_PASSWORD = "user-pw"


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(config, "EXTERNAL_URL", "http://test")
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@test.fr")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setattr(config, "SMTP_HOSTNAME", "smtp.test")
    monkeypatch.setattr(config, "SMTP_USERNAME", "sender@test.fr")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "smtp-pw")
    monkeypatch.setattr(config, "notify", True)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    # The SQLite path is relative to the working directory
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_module, "seed_races_from_ffc", lambda db, force=False: 0)
    return tmp_path


@pytest.fixture
def make_app(settings, workdir):
    def factory():
        app = app_module.create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        return app
    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def db(app):
    return app.config["repository"]


@pytest.fixture
def sent_emails(monkeypatch):
    """Captures emails instead of sending them."""
    sent = []

    def fake_send_email(to_address, subject, message):
        sent.append({"to": to_address, "subject": subject, "message": message})
        return True

    for module in ("api", "admin", "auth"):
        monkeypatch.setattr(f"engagement_course.{module}.send_email", fake_send_email)
    return sent


@pytest.fixture
def create_user(db):
    def factory(username, category=Category("OPEN", 1), **kwargs):
        return db.create_user(
            email=f"{username}@test.fr",
            username=username,
            password=USER_PASSWORD,
            firstname=username.capitalize(),
            lastname="Test",
            category=category,
            **kwargs,
        )
    return factory


@pytest.fixture
def create_race(db):
    def factory(days_ahead=20, categories=None, location="Vitré"):
        date = datetime.datetime.now() + datetime.timedelta(days=days_ahead)
        race = RaceEvent("Sam", date, location, 35, "FFC", "ROUTE", categories or [Category("OPEN", 1)])
        existing = db.list_races()
        db.replace_races(existing + [race])
        return next(r for r in db.list_races() if r.location == location)
    return factory


def login(client, username, password=USER_PASSWORD):
    return client.post("/login", data={"email_or_username": username, "password": password})
