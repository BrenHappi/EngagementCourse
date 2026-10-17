import datetime

from engagement_course.ffc_parser import FFCParser
from engagement_course.models import Category

# Minimal excerpt reproducing the structure of cyclisme-amateur.com calendar pages:
# the first race of a day has 5 cells, following races on the same day have 4.
CALENDAR_HTML = """
<table class="avec-contour">
  <tr><td><b>Mars 2027</b></td></tr>
  <tr class="ligne_de_course">
    <td>Sam 06</td><td>Vitré .</td><td>FFC</td><td>ROUTE</td><td>OPEN 1,2,3 + ACCESS 1 ET 2</td>
  </tr>
  <tr class="ligne_de_course">
    <td>Fougères</td><td>FFC</td><td>CX</td><td>ACCESS 3,4 (Féminines)</td>
  </tr>
  <tr class="ligne_de_course">
    <td>Dim 07</td><td>Redon</td><td>UFOLEP</td><td>ROUTE</td><td>Cadets</td>
  </tr>
</table>
"""


def test_parse_calendar():
    races = FFCParser(department=35).parse_calendar(CALENDAR_HTML)

    assert [(r.race_day, r.date, r.location, r.type) for r in races] == [
        ("Sam", datetime.date(2027, 3, 6), "Vitré", "ROUTE"),
        ("Sam", datetime.date(2027, 3, 6), "Fougères", "CX"),
        ("Dim", datetime.date(2027, 3, 7), "Redon", "ROUTE"),
    ]
    assert all(r.department == 35 for r in races)
    assert [c.to_key() for c in races[0].categories] == ["OPEN_1", "OPEN_2", "OPEN_3", "ACCESS_1", "ACCESS_2"]
    assert [c.to_key() for c in races[1].categories] == ["ACCESS_3", "ACCESS_4"]
    assert races[2].categories is None


def test_category_from_string_ignores_unsupported_levels():
    assert Category.from_string("Cadets + Juniors") is None
    assert [c.to_key() for c in Category.from_string("OPEN 3 + Juniors")] == ["OPEN_3"]
