import re

import pytest

from engagement_course import auth, config
from conftest import login


@pytest.fixture
def rider(create_user):
    return create_user("rider")


def request_reset(client, email):
    return client.post("/forgot-password", data={"email": email}, follow_redirects=True)


def reset_link(sent_emails):
    return re.search(r"http://test(/reset-password/\S+)", sent_emails[-1]["message"]).group(1)


def test_full_reset_flow(app, rider, sent_emails):
    client = app.test_client()
    request_reset(client, "rider@test.fr")
    assert sent_emails[-1]["to"] == "rider@test.fr"

    link = reset_link(sent_emails)
    assert client.get(link).status_code == 200
    response = client.post(link, data={"password": "new-password", "confirm_password": "new-password"})
    assert response.status_code == 302

    assert login(app.test_client(), "rider", "new-password").status_code == 302
    assert "incorrect" in login(app.test_client(), "rider").get_data(as_text=True)


def test_reset_link_is_single_use(app, rider, sent_emails):
    client = app.test_client()
    request_reset(client, "rider@test.fr")
    link = reset_link(sent_emails)
    client.post(link, data={"password": "new-password", "confirm_password": "new-password"})

    response = client.get(link, follow_redirects=True)
    assert "invalide ou a expiré" in response.get_data(as_text=True)


def test_reset_link_expires(app, rider, sent_emails, monkeypatch):
    client = app.test_client()
    request_reset(client, "rider@test.fr")
    monkeypatch.setattr(config, "PASSWORD_RESET_MAX_AGE", -1)
    response = client.get(reset_link(sent_emails), follow_redirects=True)
    assert "invalide ou a expiré" in response.get_data(as_text=True)


def test_tampered_token_rejected(app, rider):
    response = app.test_client().get("/reset-password/forged-token", follow_redirects=True)
    assert "invalide ou a expiré" in response.get_data(as_text=True)


def test_unknown_email_gives_same_answer(app, rider, sent_emails):
    known = request_reset(app.test_client(), "rider@test.fr").get_data(as_text=True)
    unknown = request_reset(app.test_client(), "nobody@test.fr").get_data(as_text=True)
    assert "Si un compte existe" in known and "Si un compte existe" in unknown
    assert len(sent_emails) == 1


def test_password_confirmation_must_match(app, rider, sent_emails):
    client = app.test_client()
    request_reset(client, "rider@test.fr")
    response = client.post(reset_link(sent_emails), data={"password": "a", "confirm_password": "b"})
    assert "ne correspondent pas" in response.get_data(as_text=True)
    assert login(app.test_client(), "rider").status_code == 302


def test_reset_unavailable_without_smtp(app, rider, sent_emails):
    app.config["notify"] = False
    response = app.test_client().get("/forgot-password", follow_redirects=True)
    assert "contactez un administrateur" in response.get_data(as_text=True)
