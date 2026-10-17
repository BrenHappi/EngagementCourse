import datetime

import pytest

from engagement_course.models import Category, RaceEvent, is_adult_categories_label, normalize_location
from conftest import ADMIN_PASSWORD, login


@pytest.mark.parametrize("label", [
    "U 23 SéNIORS + VéTéRANS",
    "U 19 + DAMES ( COUPE DE BRETAGNE )",
    "1,2 + JUNIORS",
    "3 + DAMES",
    "ELITE OPEN 1,2,3",
    "U 17 + DAMES",
    "TOUTE CATéGORIE",
])
def test_adult_labels(label):
    assert is_adult_categories_label(label)


@pytest.mark.parametrize("label", [
    "ECOLE DE CYCLISME",
    "U 15",
    "U 17 ( COUPE DE BRETAGNE )",
    "MINIME",
    "CADET",
    "U 19 HOMMES",
    "DAMES U 17 + U 15 FILLES",
    "U 23 SéNIORS + VéTéRANS ( CL GéNéRAL )",
    "",
    None,
])
def test_youth_labels(label):
    assert not is_adult_categories_label(label)


def make_race(race_type, label, categories=None, location="Lieu"):
    return RaceEvent("Sam", datetime.date(2027, 1, 9), location, 35, "FFC", race_type, categories, categories_label=label)


def test_normalize_location():
    assert normalize_location("Pleven ( la chauvinais ).") == "Pleven ( la chauvinais )"
    assert normalize_location("Lamballe  armor .") == "Lamballe armor"


def test_relevant_races():
    assert make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS").is_relevant()
    assert not make_race("CYCLO-CROSS", "U 17").is_relevant()
    assert make_race("ROUTE", "OPEN 1", [Category("OPEN", 1)]).is_relevant()
    assert not make_race("ROUTE", "Cadets").is_relevant()
    assert not make_race("VTT", "OPEN 1", [Category("OPEN", 1)]).is_relevant()


@pytest.fixture
def cx_race(create_race):
    return create_race(race_type="CYCLO-CROSS", categories_label="U 23 SéNIORS + VéTéRANS", location="Guipel")


def cx(label, location="Nozay"):
    return make_race("CYCLO-CROSS", label, Category.from_string(label), location=location)


@pytest.fixture
def nozay(db):
    # Real-life event: OPEN and ACCESS races, age-group races, and a second posting of the same races
    db.replace_races([
        cx("OPEN 1,2,3"), cx("ACCESS 1,2,3,4"), cx("U 19 + DAMES"), cx("U 17"), cx("ECOLE DE CYCLISME"),
        cx("ELITE OPEN 1,2,3", "Nozay ( la ville au chef )."), cx("ACCESS 1,2,3,4", "Nozay ( la ville au chef )."),
    ])
    return {(r.categories_label if not r.categories else " ".join(c.to_key() for c in r.categories)): r for r in db.list_races()}


def test_cyclocross_open_and_access_races_are_separate_entries(nozay):
    assert sorted(nozay) == ["ACCESS_1 ACCESS_2 ACCESS_3 ACCESS_4", "OPEN_1 OPEN_2 OPEN_3", "U 19 + DAMES"]
    assert nozay["OPEN_1 OPEN_2 OPEN_3"].requires_category_match
    assert not nozay["U 19 + DAMES"].requires_category_match


def test_cyclocross_open_race_checks_rider_category(app, db, nozay, create_user, sent_emails):
    rider = create_user("access", category=Category("ACCESS", 4))
    client = app.test_client()
    login(client, "access")
    engage = lambda race: client.post("/api/v1/engagement", json={"user_id": rider, "race_id": race.id, "status": "pending"})
    assert engage(nozay["OPEN_1 OPEN_2 OPEN_3"]).status_code == 400
    assert engage(nozay["ACCESS_1 ACCESS_2 ACCESS_3 ACCESS_4"]).status_code == 201
    assert engage(nozay["U 19 + DAMES"]).status_code == 201


def test_category_filter_on_cyclocross(db, nozay):
    from engagement_course.models import RaceFilter
    races = db.search_races(RaceFilter(category=[Category("ACCESS", 4)]))
    assert sorted(r.id for r in races) == sorted([nozay["ACCESS_1 ACCESS_2 ACCESS_3 ACCESS_4"].id, nozay["U 19 + DAMES"].id])


def test_reimport_keeps_cyclocross_ids(db, nozay):
    db.replace_races([cx("U 19 + DAMES"), cx("ACCESS 1,2,3,4"), cx("OPEN 1,2,3")])  # different order
    after = {(r.categories_label if not r.categories else " ".join(c.to_key() for c in r.categories)): r.id for r in db.list_races()}
    assert after == {key: race.id for key, race in nozay.items()}


def test_cyclocross_event_stored_once(db):
    # The FFC calendar lists one row per category race of the same event
    db.replace_races([
        make_race("CYCLO-CROSS", "ECOLE DE CYCLISME"),
        make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS"),
        make_race("CYCLO-CROSS", "U 19 + DAMES"),
        make_race("CYCLO-CROSS", "3 + DAMES"),
    ])
    [race] = db.list_races()
    assert race.categories_label == "U 23 SéNIORS + VéTéRANS · U 19 + DAMES · 3 + DAMES"

    # Re-importing keeps a single entry
    db.replace_races([make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS"), make_race("CYCLO-CROSS", "3 + DAMES")])
    assert len(db.list_races()) == 1


def test_youth_cyclocross_not_stored(db, create_race):
    db.replace_races([make_race("CYCLO-CROSS", "ECOLE DE CYCLISME")])
    assert db.list_races() == []


def test_any_rider_can_engage_on_cyclocross(app, create_user, cx_race, sent_emails):
    rider = create_user("access", category=Category("ACCESS", 4))
    client = app.test_client()
    login(client, "access")
    response = client.post("/api/v1/engagement", json={"user_id": rider, "race_id": cx_race.id, "status": "pending"})
    assert response.status_code == 201


def test_cyclocross_visible_with_category_filter(app, create_user, cx_race):
    create_user("rider", category=Category("OPEN", 1))
    client = app.test_client()
    login(client, "rider")
    month = cx_race.date
    html = client.get(f"/?month={month.month}&year={month.year}").get_data(as_text=True)
    assert "Guipel" in html
    assert "U 23 S" in html


def test_manager_sees_cyclocross_engagement_of_riders_in_managed_category(db, create_user, cx_race):
    open_rider = create_user("openrider", category=Category("OPEN", 1))
    access_rider = create_user("accessrider", category=Category("ACCESS", 4))
    db.create_engagement(open_rider, cx_race, "pending")
    db.create_engagement(access_rider, cx_race, "pending")

    managed = db.list_engagements(status="pending", categories=[Category("OPEN", 1)])
    assert [e.user.username for e in managed] == ["openrider"]


def test_admin_engagements_page_shows_cyclocross_label(app, db, create_user, cx_race):
    rider = create_user("rider", category=Category("OPEN", 1))
    db.create_engagement(rider, cx_race, "pending")
    client = app.test_client()
    login(client, "admin", ADMIN_PASSWORD)
    html = client.get("/admin/engagements").get_data(as_text=True)
    assert "GUIPEL" in html and "CYCLO-CROSS" in html


def test_cyclocross_rows_merged_despite_location_typos(db):
    db.replace_races([
        make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS", location="Pleudihen/rance."),
        make_race("CYCLO-CROSS", "U 19 + DAMES", location="Pleuhidan/rance"),
        make_race("CYCLO-CROSS", "1,2 + JUNIORS", location="Pleven ( la chauvinais )."),
    ])
    races = {r.location: r.categories_label for r in db.list_races()}
    assert races == {
        "Pleudihen/rance": "U 23 SéNIORS + VéTéRANS · U 19 + DAMES",
        "Pleven ( la chauvinais )": "1,2 + JUNIORS",
    }


def test_existing_duplicates_cleaned_on_reimport(db):
    # Rows stored by a previous import, before merging
    db.replace_races([make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS", location="Pleudihen/rance.")])
    with db._connect() as conn:
        conn.execute("UPDATE races SET location = 'Pleudihen/rance.'")
    db.replace_races([
        make_race("CYCLO-CROSS", "U 23 SéNIORS + VéTéRANS", location="Pleudihen/rance."),
        make_race("CYCLO-CROSS", "U 19 + DAMES", location="Pleuhidan/rance"),
    ])
    [race] = db.list_races()
    assert race.location == "Pleudihen/rance"


def test_road_races_of_same_event_kept_separate(db):
    # Same day and place but distinct races (OPEN / ACCESS): each one must be kept
    db.replace_races([
        make_race("ROUTE", "OPEN 1,2,3", [Category("OPEN", 1)]),
        make_race("ROUTE", "ACCESS 1 ET 2", [Category("ACCESS", 1)]),
    ])
    assert sorted(c.to_key() for r in db.list_races() for c in r.categories) == ["ACCESS_1", "OPEN_1"]


def test_reimport_keeps_road_races_of_same_event_and_their_ids(db):
    races = lambda: [
        make_race("ROUTE", "OPEN 1,2,3", [Category("OPEN", 1)]),
        make_race("ROUTE", "ACCESS 1 ET 2", [Category("ACCESS", 1)]),
    ]
    db.replace_races(races())
    before = {r.id: [c.to_key() for c in r.categories] for r in db.list_races()}
    db.replace_races(races())
    after = {r.id: [c.to_key() for c in r.categories] for r in db.list_races()}
    assert after == before
