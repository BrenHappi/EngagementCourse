import datetime

import pytest

from engagement_course.models import Category, RecapSettings
from engagement_course.recap import is_due, send_due_recaps, upcoming_weekend
from conftest import ADMIN_PASSWORD, login

ADMIN_ID = 1  # Created at startup, manages every category


def test_upcoming_weekend():
    saturday, sunday = datetime.date(2026, 10, 24), datetime.date(2026, 10, 25)
    assert upcoming_weekend(datetime.date(2026, 10, 20)) == (saturday, sunday)  # Tuesday
    assert upcoming_weekend(saturday) == (saturday, sunday)
    assert upcoming_weekend(sunday) == (saturday, sunday)


@pytest.mark.parametrize("settings, now, expected", [
    (RecapSettings(), datetime.datetime(2026, 10, 20, 19, 0), True),
    (RecapSettings(), datetime.datetime(2026, 10, 20, 22, 0), True),  # Catch-up after a missed run
    (RecapSettings(), datetime.datetime(2026, 10, 20, 18, 59), False),
    (RecapSettings(), datetime.datetime(2026, 10, 21, 19, 0), False),
    (RecapSettings(enabled=False), datetime.datetime(2026, 10, 20, 19, 0), False),
    (RecapSettings(last_sent_on=datetime.date(2026, 10, 20)), datetime.datetime(2026, 10, 20, 21, 0), False),
    (RecapSettings(weekday=0, hour=7), datetime.datetime(2026, 10, 19, 7, 0), True),
])
def test_is_due(settings, now, expected):
    assert is_due(settings, now) == expected


@pytest.fixture
def saturday():
    """A Saturday far enough ahead for engagements to still be open."""
    today = datetime.date.today()
    return today + datetime.timedelta(days=(5 - today.weekday()) % 7 + 14)


@pytest.fixture
def tuesday_evening(saturday):
    return datetime.datetime.combine(saturday - datetime.timedelta(days=4), datetime.time(19, 30))


@pytest.fixture
def weekend_race(create_race, saturday):
    return create_race(days_ahead=(saturday - datetime.date.today()).days, location="Rennes")


def test_recap_lists_weekend_pending_engagements(db, create_user, create_race, saturday, tuesday_evening, weekend_race, sent_emails):
    rider = create_user("rider", category=Category("OPEN", 1))
    db.create_engagement(rider, weekend_race, "pending")
    next_week = create_race(days_ahead=(saturday - datetime.date.today()).days + 7, location="Brest")
    db.create_engagement(rider, next_week, "pending")

    assert send_due_recaps(db, tuesday_evening, "http://test") == 1
    [mail] = sent_emails
    assert mail["to"] == "admin@test.fr"
    assert mail["subject"] == f"1 inscription à valider pour le week-end du {saturday:%d/%m}"
    assert "Rider Test (OPEN 1)" in mail["message"]
    assert "Rennes" in mail["message"]
    assert "Brest" not in mail["message"]
    assert "http://test/admin/engagements" in mail["message"]


def test_recap_sent_once_per_day(db, create_user, tuesday_evening, weekend_race, sent_emails):
    db.create_engagement(create_user("rider"), weekend_race, "pending")
    send_due_recaps(db, tuesday_evening, "http://test")
    send_due_recaps(db, tuesday_evening + datetime.timedelta(hours=1), "http://test")
    assert len(sent_emails) == 1


def test_no_email_without_pending_engagement(db, create_user, tuesday_evening, weekend_race, sent_emails):
    db.create_engagement(create_user("rider"), weekend_race, "validated")
    assert send_due_recaps(db, tuesday_evening, "http://test") == 0
    assert sent_emails == []


def test_recap_limited_to_managed_categories(db, create_user, tuesday_evening, weekend_race, sent_emails):
    db.update_user(ADMIN_ID, managed_categories=[Category("ACCESS", 1)])
    db.create_engagement(create_user("rider", category=Category("OPEN", 1)), weekend_race, "pending")
    send_due_recaps(db, tuesday_evening, "http://test")
    assert sent_emails == []


def test_disabled_recap_not_sent(db, create_user, tuesday_evening, weekend_race, sent_emails):
    db.update_recap_settings(ADMIN_ID, enabled=False, weekday=1, hour=19)
    db.create_engagement(create_user("rider"), weekend_race, "pending")
    send_due_recaps(db, tuesday_evening, "http://test")
    assert sent_emails == []


def test_failed_email_retried_next_run(db, create_user, tuesday_evening, weekend_race, monkeypatch):
    db.create_engagement(create_user("rider"), weekend_race, "pending")
    monkeypatch.setattr("engagement_course.recap.send_email", lambda **kwargs: False)
    send_due_recaps(db, tuesday_evening, "http://test")
    assert db.get_recap_settings(ADMIN_ID).last_sent_on is None


def profile_data(**extra):
    data = {"profile-firstname": "", "profile-lastname": "", "profile-username": "", "profile-category": "", "profile-address": ""}
    data.update(extra)
    return data


def test_admin_configures_recap_from_profile(app, db):
    client = app.test_client()
    login(client, "admin", ADMIN_PASSWORD)
    html = client.get("/profile").get_data(as_text=True)
    assert '<input checked id="profile-recap_enabled"' in html

    response = client.post("/profile", data=profile_data(**{"profile-recap_weekday": "4", "profile-recap_hour": "8"}))
    assert response.status_code == 302
    settings = db.get_recap_settings(ADMIN_ID)
    assert (settings.enabled, settings.weekday, settings.hour) == (False, 4, 8)


def test_regular_user_profile_still_saves(app, db, create_user):
    rider = create_user("rider")
    client = app.test_client()
    login(client, "rider")
    assert "Récap hebdomadaire" not in client.get("/profile").get_data(as_text=True)
    response = client.post("/profile", data=profile_data(**{"profile-firstname": "Renamed"}))
    assert response.status_code == 302
    assert db.get_user_by_id(rider).firstname == "Renamed"
