import pytest

from engagement_course.models import Category
from conftest import ADMIN_PASSWORD, login


@pytest.fixture
def admin_client(app):
    client = app.test_client()
    login(client, "admin", ADMIN_PASSWORD)
    return client


def managed_keys(db, user_id):
    return sorted(c.to_key() for c in db.get_user_by_id(user_id).managed_categories or [])


def update_user(client, db, user_id, **extra):
    # Mirrors the inline edit row: every field is submitted with its current value
    user = db.get_user_by_id(user_id)
    data = {
        "_action": "update_user",
        "user_id": user_id,
        "firstname": user.firstname,
        "lastname": user.lastname,
        "username": user.username,
        "email": user.email,
        "category": user.category.to_key() if user.category else "",
        "role": user.role,
    }
    data.update(extra)
    return client.post("/admin/users", data=data)


def test_admin_sets_managed_categories_of_another_admin(admin_client, db, create_user):
    chef = create_user("chef", role="admin")
    response = update_user(admin_client, db, chef, managed_categories_submitted="1", managed_categories=["OPEN_2", "ACCESS_1"])
    assert response.status_code == 302
    assert managed_keys(db, chef) == ["ACCESS_1", "OPEN_2"]


def test_unchecking_every_category_clears_them(admin_client, db, create_user):
    chef = create_user("chef", role="admin", managed_categories=[Category("OPEN", 1)])
    update_user(admin_client, db, chef, managed_categories_submitted="1")
    assert managed_keys(db, chef) == []


def test_update_without_category_editor_keeps_them(admin_client, db, create_user):
    chef = create_user("chef", role="admin", managed_categories=[Category("OPEN", 1)])
    update_user(admin_client, db, chef, firstname="Nouveau")
    assert managed_keys(db, chef) == ["OPEN_1"]
    assert db.get_user_by_id(chef).firstname == "Nouveau"


def test_managed_categories_ignored_for_regular_users(admin_client, db, create_user):
    rider = create_user("rider")
    update_user(admin_client, db, rider, managed_categories_submitted="1", managed_categories=["OPEN_1"])
    assert db.get_user_by_id(rider).managed_categories is None


def test_create_admin_with_managed_categories(admin_client, db):
    response = admin_client.post("/admin/users", data={
        "_action": "create_user",
        "firstname": "Anne",
        "lastname": "Chef",
        "email": "anne@test.fr",
        "password": "pw",
        "role": "admin",
        "managed_categories": ["ACCESS_3", "ACCESS_4"],
    })
    assert response.status_code == 302
    assert managed_keys(db, db.get_user_by_email("anne@test.fr").user_id) == ["ACCESS_3", "ACCESS_4"]


def test_users_page_shows_managed_categories(admin_client, db, create_user):
    create_user("chef", role="admin", managed_categories=[Category("ACCESS", 2)])
    html = admin_client.get("/admin/users").get_data(as_text=True)
    assert 'name="managed_categories" value="ACCESS_2" checked' in html
