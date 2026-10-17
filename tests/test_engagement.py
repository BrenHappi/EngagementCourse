import smtplib

import pytest

from engagement_course.models import Category
from conftest import login


@pytest.fixture
def rider(create_user):
    return create_user("rider", category=Category("OPEN", 1))


def engage(app, username, user_id, race_id, status="pending"):
    client = app.test_client()
    login(client, username)
    return client.post("/api/v1/engagement", json={"user_id": user_id, "race_id": race_id, "status": status})


def test_engagement_notifies_category_manager(app, rider, create_race, sent_emails):
    race = create_race()
    response = engage(app, "rider", rider, race.id)
    assert response.status_code == 201
    assert [mail["to"] for mail in sent_emails] == ["admin@test.fr"]


def test_interested_does_not_notify(app, rider, create_race, sent_emails):
    race = create_race()
    assert engage(app, "rider", rider, race.id, status="interested").status_code == 201
    assert sent_emails == []


def test_duplicate_engagement_rejected(app, rider, create_race, sent_emails):
    race = create_race()
    assert engage(app, "rider", rider, race.id).status_code == 201
    assert engage(app, "rider", rider, race.id).status_code == 400


def test_engagements_close_five_days_before_race(app, rider, create_race, sent_emails):
    assert engage(app, "rider", rider, create_race(days_ahead=4, location="Proche").id).status_code == 400
    assert engage(app, "rider", rider, create_race(days_ahead=6, location="Loin").id).status_code == 201


def test_category_must_match_race(app, create_user, create_race, sent_emails):
    rider = create_user("access", category=Category("ACCESS", 4))
    race = create_race(categories=[Category("OPEN", 1)])
    assert engage(app, "access", rider, race.id).status_code == 400


def test_cannot_engage_another_user(app, rider, create_user, create_race, sent_emails):
    other = create_user("other")
    race = create_race()
    assert engage(app, "rider", other, race.id).status_code == 403


def test_user_cannot_self_validate(app, rider, create_race, sent_emails):
    race = create_race()
    assert engage(app, "rider", rider, race.id, status="validated").status_code == 403


def test_no_manager_for_category_still_creates_engagement(app, db, create_user, create_race, sent_emails):
    db.update_user(1, managed_categories=[Category("OPEN", 1)])
    rider = create_user("access", category=Category("ACCESS", 4))
    race = create_race(categories=[Category("ACCESS", 4)])
    assert engage(app, "access", rider, race.id).status_code == 201
    assert sent_emails == []


def test_smtp_failure_still_creates_engagement(app, db, rider, create_race, monkeypatch):
    def unreachable(*args, **kwargs):
        raise ConnectionRefusedError("SMTP down")
    monkeypatch.setattr(smtplib, "SMTP", unreachable)

    race = create_race()
    assert engage(app, "rider", rider, race.id).status_code == 201
    assert len(db.list_engagements(user_id=rider)) == 1


def test_admin_warned_when_rider_notification_fails(app, db, rider, create_race, monkeypatch, sent_emails):
    from conftest import ADMIN_PASSWORD
    race = create_race()
    engage(app, "rider", rider, race.id)
    engagement = db.list_engagements(user_id=rider)[0]
    monkeypatch.setattr("engagement_course.admin.send_email", lambda **kwargs: False)

    client = app.test_client()
    login(client, "admin", ADMIN_PASSWORD)
    response = client.post("/admin/engagements", data={"engagement_id": engagement.id, "status": "validated"}, follow_redirects=True)
    assert "pas pu être envoyé" in response.get_data(as_text=True)
    assert db.get_engagement_by_id(engagement.id).status == "validated"
