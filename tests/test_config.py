import pytest

import engagement_course.app as app_module
from engagement_course import config


@pytest.mark.parametrize("name", ["SECRET_KEY", "EXTERNAL_URL"])
def test_missing_required_setting_prevents_startup(settings, workdir, monkeypatch, name):
    monkeypatch.setattr(config, name, None)
    with pytest.raises(RuntimeError, match=name):
        app_module.create_app()


def test_admin_credentials_required_to_create_initial_admin(settings, workdir, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", None)
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        app_module.create_app()


def test_admin_credentials_not_required_once_admin_exists(make_app, monkeypatch):
    make_app()
    monkeypatch.setattr(config, "ADMIN_PASSWORD", None)
    make_app()


def test_health(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
