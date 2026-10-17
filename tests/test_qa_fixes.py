from engagement_course.models import Category
from conftest import ADMIN_PASSWORD, USER_PASSWORD, login


def client_for(app, username, password=USER_PASSWORD):
    client = app.test_client()
    login(client, username, password)
    return client


def test_login_ignores_email_case(app, create_user):
    create_user("rider")
    response = login(app.test_client(), "RIDER@Test.FR")
    assert response.status_code == 302


def test_login_returns_to_requested_page_on_this_site_only(app, create_user):
    create_user("rider")
    response = app.test_client().post("/login?next=/profile", data={"email_or_username": "rider", "password": USER_PASSWORD})
    assert response.headers["Location"] == "/profile"
    response = app.test_client().post("/login?next=//evil.example", data={"email_or_username": "rider", "password": USER_PASSWORD})
    assert response.headers["Location"] == "/"


def test_interested_to_pending_respects_closing_and_notifies(app, db, create_user, create_race, sent_emails):
    rider = create_user("rider")
    soon = create_race(days_ahead=3, location="Proche")
    later = create_race(days_ahead=20, location="Loin")
    db.create_engagement(rider, soon, "interested")
    db.create_engagement(rider, later, "interested")
    client = client_for(app, "rider")
    soon_id, later_id = (db.list_engagements(user_id=rider)[i].id for i in (0, 1))
    soon_id, later_id = sorted([soon_id, later_id], key=lambda i: db.get_engagement_by_id(i).race.date)

    assert client.patch(f"/api/v1/engagement/{soon_id}", json={"status": "pending"}).status_code == 400
    assert client.patch(f"/api/v1/engagement/{later_id}", json={"status": "pending"}).status_code == 200
    assert [mail["to"] for mail in sent_emails] == ["admin@test.fr"]


def test_withdrawal_from_validated_race_notifies_manager(app, db, create_user, create_race, sent_emails):
    rider = create_user("rider")
    db.create_engagement(rider, create_race(), "validated")
    engagement_id = db.list_engagements(user_id=rider)[0].id
    response = client_for(app, "rider").patch(f"/api/v1/engagement/{engagement_id}", json={"status": "cancelled"})
    assert response.status_code == 200
    assert "Désistement" in sent_emails[0]["subject"]


def test_dedicated_manager_is_notified_rather_than_global_admin(app, create_user, create_race, sent_emails):
    create_user("chef", role="admin", managed_categories=[Category("OPEN", 1)])
    rider = create_user("rider")
    response = client_for(app, "rider").post("/api/v1/engagement", json={"user_id": rider, "race_id": create_race().id, "status": "pending"})
    assert response.status_code == 201
    assert [mail["to"] for mail in sent_emails] == ["chef@test.fr"]


def test_rider_without_category_can_ask_for_open_cyclocross(app, create_user, create_race, sent_emails):
    rider = create_user("rider", category=None)
    race = create_race(race_type="CYCLO-CROSS", categories=None, categories_label="U 23 SENIORS + VETERANS")
    response = client_for(app, "rider").post("/api/v1/engagement", json={"user_id": rider, "race_id": race.id, "status": "pending"})
    assert response.status_code == 201


def test_api_errors_are_in_french(app, create_user, create_race, sent_emails):
    rider = create_user("rider")
    race = create_race(days_ahead=2)
    response = client_for(app, "rider").post("/api/v1/engagement", json={"user_id": rider, "race_id": race.id, "status": "pending"})
    assert response.get_json()["message"] == "Les inscriptions sont closes pour cette course"


def test_registration_generates_free_username(app, db, create_user):
    create_user("jdupont")
    token = db.get_registration_token()
    response = app.test_client().post("/register", data={
        "registration_token": token, "firstname": "Jean", "lastname": "Dupont", "category": "OPEN_1",
        "email": "jean@test.fr", "password": "secret", "confirm_password": "secret",
    })
    assert response.status_code == 302
    assert db.get_user_by_email("jean@test.fr").username == "jdupont2"


def test_registration_requires_matching_passwords(app, db):
    token = db.get_registration_token()
    response = app.test_client().post("/register", data={
        "registration_token": token, "firstname": "Jean", "lastname": "Dupont", "category": "OPEN_1",
        "email": "jean@test.fr", "password": "secret", "confirm_password": "other",
    })
    assert "pas identiques" in response.get_data(as_text=True)
    assert db.get_user_by_email("jean@test.fr") is None


def test_admin_cannot_delete_or_demote_himself(app, db):
    client = client_for(app, "admin", ADMIN_PASSWORD)
    client.post("/admin/users", data={"_action": "delete_user", "user_id": 1})
    assert db.get_user_by_id(1) is not None
    client.post("/admin/users", data={"_action": "update_user", "user_id": 1, "role": "user"})
    assert db.get_user_by_id(1).role == "admin"


def test_validation_email_is_in_french(app, db, create_user, create_race, sent_emails):
    rider = create_user("rider")
    db.create_engagement(rider, create_race(), "pending")
    engagement_id = db.list_engagements(user_id=rider)[0].id
    client_for(app, "admin", ADMIN_PASSWORD).post("/admin/engagements", data={"engagement_id": engagement_id, "status": "validated"})
    assert sent_emails[-1]["subject"] == "Votre inscription à Vitré a été validée"


def test_profile_email_must_stay_unique(app, db, create_user):
    create_user("other")
    rider = create_user("rider")
    client_for(app, "rider").post("/profile", data={"profile-email": "other@test.fr"})
    assert db.get_user_by_id(rider).email == "rider@test.fr"
    client_for(app, "rider").post("/profile", data={"profile-email": "new@test.fr"})
    assert db.get_user_by_id(rider).email == "new@test.fr"


def test_my_races_lists_every_upcoming_month(app, db, create_user, create_race):
    rider = create_user("rider", category=Category("ACCESS", 1))
    far = create_race(days_ahead=80, location="Lointaine", categories=[Category("OPEN", 2)])
    db.create_engagement(rider, far, "interested")
    html = client_for(app, "rider").get("/?my_engagements=1").get_data(as_text=True)
    assert "Lointaine" in html
