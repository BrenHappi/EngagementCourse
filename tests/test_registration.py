from conftest import ADMIN_PASSWORD, login


def register(client, token, email="new@test.fr"):
    return client.post("/register", data={
        "registration_token": token,
        "firstname": "Jean",
        "lastname": "Dupont",
        "category": "OPEN_1",
        "email": email,
        "password": "secret-pw",
        "confirm_password": "secret-pw",
    })


def test_register_requires_valid_token(app):
    client = app.test_client()
    assert client.get("/register").status_code == 403
    assert client.get("/register?_t=wrong").status_code == 403
    assert register(client, "wrong").status_code == 403


def test_register_with_valid_token(app, db):
    token = db.get_registration_token()
    client = app.test_client()
    assert client.get(f"/register?_t={token}").status_code == 200
    assert register(client, token).status_code == 302
    assert db.get_user_by_email("new@test.fr") is not None


def test_token_shared_across_app_instances(make_app):
    # Simulates two gunicorn workers sharing the same database
    worker_1, worker_2 = make_app(), make_app()
    token = worker_1.config["repository"].get_registration_token()
    assert worker_2.config["repository"].get_registration_token() == token
    assert register(worker_2.test_client(), token).status_code == 302


def test_admin_page_shows_link_and_regeneration_invalidates_it(app, db):
    client = app.test_client()
    login(client, "admin", ADMIN_PASSWORD)
    old_token = db.get_registration_token()
    assert old_token in client.get("/admin/users").get_data(as_text=True)

    response = client.post("/admin/users", data={"_action": "regenerate_registration_token"})
    assert response.status_code == 302

    new_token = db.get_registration_token()
    assert new_token != old_token
    assert client.get(f"/register?_t={old_token}").status_code == 403
    assert client.get(f"/register?_t={new_token}").status_code == 200
