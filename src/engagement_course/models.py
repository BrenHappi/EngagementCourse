from datetime import date
from enum import Enum
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional
from dataclasses import dataclass
from bcrypt import checkpw
import flask_login

from engagement_course.config import DATE_FORMAT

USER_ROLES = {
    1: "admin",
    2: "user"
}

CATEGORIES = {
    "OPEN": [1, 2, 3],
    "ACCESS": [1, 2, 3, 4],
}


# Race types imported from the FFC calendar
ROAD_RACE_TYPE = "ROUTE"
CYCLOCROSS_RACE_TYPE = "CYCLO-CROSS"
# Race types whose categories are not OPEN/ACCESS: any rider can ask, the manager checks
CATEGORY_FREE_RACE_TYPES = (CYCLOCROSS_RACE_TYPE,)

_YOUTH_MARKERS = ("ECOLE", "MINIME", "CADET", "U 15", "U 17", "U15", "U17")
_ADULT_MARKERS = ("SENIOR", "VETERAN", "ESPOIR", "ELITE", "OPEN", "ACCESS", "DAMES", "TOUTE")


def _normalize_text(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).upper()


def normalize_location(location: str) -> str:
    """Cleans an FFC location: "Pleven ( la chauvinais ).", "Vitré ." -> "Pleven ( la chauvinais )", "Vitré"."""
    return " ".join(location.split()).rstrip(" .")


def _same_place(location_a: str, location_b: str) -> bool:
    # Compare town names only, tolerating typos of the source ("Pleudihen" / "Pleuhidan")
    a, b = (re.sub(r"[^A-Z0-9]", "", _normalize_text(loc.split("(")[0])) for loc in (location_a, location_b))
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.75


def merge_cyclocross_events(races: list["RaceEvent"]) -> list["RaceEvent"]:
    """
    The FFC calendar lists one row per category race of a cyclo-cross event.
    - OPEN/ACCESS races are kept as separate entries, like road races, so each rider
      engages in his own category (duplicates of the same race are dropped)
    - adult age-group races (U23/Séniors/Vétérans, U19 + Dames...) are merged into one
      entry open to every rider, labelled with these races
    Youth races are dropped.
    """
    merged: list[RaceEvent] = []

    def find_entry(race: "RaceEvent", category_keys: list[str]) -> "RaceEvent | None":
        return next(
            (
                e for e in merged
                if e.type == CYCLOCROSS_RACE_TYPE
                and (e.date, e.department, e.federation) == (race.date, race.department, race.federation)
                and sorted(c.to_key() for c in e.categories or []) == category_keys
                and _same_place(e.location, race.location)
            ),
            None,
        )

    for race in races:
        if race.type != CYCLOCROSS_RACE_TYPE:
            merged.append(race)
            continue
        if not is_adult_categories_label(race.categories_label):
            continue

        label = " ".join(race.categories_label.split("(")[0].split())
        category_keys = sorted(c.to_key() for c in race.categories or [])
        entry = find_entry(race, category_keys)
        if race.categories:
            if entry is None:
                merged.append(race)
            continue

        if entry is None:
            entry = RaceEvent(race.race_day, race.date, race.location, race.department, race.federation, race.type, None)
            entry.age_group_races = []
            merged.append(entry)
        if label not in entry.age_group_races:
            entry.age_group_races.append(label)
        entry.categories_label = " · ".join(entry.age_group_races)
    return merged


def is_adult_categories_label(label: str | None) -> bool:
    """
    Tells whether a raw FFC category label is open to adult riders, i.e. one of its
    "+"-separated groups is an adult one.
    e.g. "U 23 SéNIORS + VéTéRANS", "1,2 + JUNIORS", "U 17 + DAMES" -> True
         "ECOLE DE CYCLISME", "U 17", "DAMES U 17 + U 15 FILLES" -> False
    """
    if not label:
        return False
    if "CL GENERAL" in _normalize_text(label):
        return False  # season ranking, not a race
    text = _normalize_text(label.split("(")[0])  # drop event details, e.g. "( COUPE DE BRETAGNE )"
    for group in text.split("+"):
        group = group.strip()
        if any(marker in group for marker in _YOUTH_MARKERS):
            continue
        # Groups starting with a number are cyclo-cross levels, e.g. "1,2" in "1,2 + JUNIORS"
        if group[:1].isdigit() or any(marker in group for marker in _ADULT_MARKERS):
            return True
    return False


class EngagementStatus(str, Enum):
    NONE = "none"
    INTERESTED = "interested"
    PENDING = "pending"
    VALIDATED = "validated"
    CANCELLED = "cancelled"
    

class Category:
    def __init__(self, level: str, number: int):
        self.level = level
        self.number = number
    
    def __repr__(self):
        return f"{self.level} {self.number}"
    
    @staticmethod
    def from_string(raw_category: str) -> list["Category"] | None:
        """
        Converts a raw category string into a list of Category objects.

        Args:
            raw_category: The raw category string (e.g., "OPEN 1,2,3 + ACCESS 1 ET 2").
        Returns:
            A list of Category objects or None if no valid categories are found.
        """
        if raw_category is None:
            return None
        
        # Remove the parenthetical part if it exists (e.g., "(Féminines)" in "OPEN 1,2,3 + ACCESS 1 ET 2 (Féminines)")
        pattern = r"(\([^\)]+\)?)"
        match = re.search(pattern, raw_category)
        if match:
            raw_category = raw_category.replace(match.group(0), "").strip()

        category_labels = CATEGORIES.keys()
        categories = []
        for part in raw_category.split('+'):
            level = next((label for label in category_labels if label in part), None)
            if level is None:
                continue  # Skip unsupported categories
            for c in part:
                if c.isdigit():
                    categories.append(Category(level=level, number=int(c)))
        return categories if categories else None

    @staticmethod
    def from_key(key: str) -> "Category | None":
        """
        Converts a category key (e.g., "OPEN_1") into a Category object.
        Args:
            key: The category key string. (e.g., "OPEN_1")
        Returns:
            A Category object or None if the key is invalid. 
            e.g., "OPEN_1" -> Category(level="OPEN", number=1)
        """
        if key is None:
            return None
        parts = key.split("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return Category(level=parts[0], number=int(parts[1]))
        return None
    
    @staticmethod
    def get_category_options() -> list[tuple[str, str]]:
        """
        Generates a list of category options for form selection.
        Returns:
            A list of tuples where each tuple contains a category key and its display name.
            e.g., [("OPEN_1", "OPEN 1"), ("ACCESS_2", "ACCESS 2"), ...]
        """
        options: list[tuple[str, str]] = []
        for level, numbers in CATEGORIES.items():
            for number in numbers:
                key = f"{level}_{number}"
                options.append((key, f"{level} {number}"))
        return options

    def to_key(self) -> str:
        return f"{self.level}_{self.number}"    


class RaceEvent:
    def __init__(
        self,
        race_day: str,
        date: date,
        location: str,
        department: int,
        federation: str,
        type: str,
        categories: list[Category],
        id: Optional[int] = None,
        location_lat: Optional[float] = None,
        location_lon: Optional[float] = None,
        categories_label: Optional[str] = None,
    ):
        self.id = id
        self.race_day = race_day
        self.date = date
        self.location = location
        self.location_lat = location_lat
        self.location_lon = location_lon
        self.department = department
        self.federation = federation
        self.type = type
        self.categories = categories
        self.categories_label = categories_label  # FFC label; for cyclo-cross, the adult races of the event
        self.distance_km: Optional[float] = None
        # engagements
        self.engagements: list[Engagement] = []
        self.validated_users: list[User] = []
        self.pending_users: list[User] = []
        self.interested_users: list[User] = []
        self.my_status = EngagementStatus.NONE

    def __repr__(self):
        return f"RaceEvent(id={self.id}, race_day='{self.race_day}', date={self.date}, location='{self.location}', department={self.department}, categories={self.categories})"
    
    def display_date(self) -> str:
        return self.date.strftime(DATE_FORMAT)

    @property
    def requires_category_match(self) -> bool:
        # Cyclo-cross age-group races are open to every rider, its OPEN/ACCESS races are not
        return self.type not in CATEGORY_FREE_RACE_TYPES or bool(self.categories)

    def is_relevant(self) -> bool:
        """Races stored in the club calendar: road races open to OPEN/ACCESS, and adult cyclo-cross."""
        if self.type == ROAD_RACE_TYPE:
            return bool(self.categories)
        if self.type == CYCLOCROSS_RACE_TYPE:
            return is_adult_categories_label(self.categories_label)
        return False


@dataclass(slots=True)
class RaceFilter:
    id: Optional[int] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    location: Optional[str] = None
    department: Optional[list[int]] = None
    federation: Optional[str] = None
    type: Optional[str] = None
    category: Optional[list[Category]] = None


class User(flask_login.UserMixin):
    user_id: int
    firstname: str
    lastname: str
    email: str
    username: str
    password_hash: bytes
    category: Category
    role: str
    managed_categories: Optional[list[Category]] = None
    address: Optional[str] = None
    address_lat: Optional[float] = None
    address_lon: Optional[float] = None

    def __init__(self, email: str, username: str, password_hash: bytes, firstname: str, lastname: str, role: str = "user", category: Optional[Category] = None, managed_categories: Optional[list[Category]] = None, user_id: Optional[int] = None, address: Optional[str] = None, address_lat: Optional[float] = None, address_lon: Optional[float] = None):
        self.user_id = user_id
        self.id = user_id
        self.firstname = firstname
        self.lastname = lastname
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.category = category
        self.address = address
        self.address_lat = address_lat
        self.address_lon = address_lon
        if role not in USER_ROLES.values():
            self.role = "user"  # Default to "user"
        else:
            self.role = role
        
        if self.role == "admin":
            self.managed_categories = managed_categories

    def __repr__(self):
        return f"{self.username} ({self.firstname} {self.lastname}) [{self.category}]"

    def verify_password(self, password: str) -> bool:
        return checkpw(password.encode('utf-8'), self.password_hash)
    

class Engagement:
    def __init__(self, user: User, race: RaceEvent, status: str, id: Optional[int] = None):
        self.id = id
        self.user = user
        self.race = race
        self.status = status  # e.g., "validated", "pending", "cancelled"

    def __repr__(self):
        return f"Engagement(id={self.id}, user={self.user}, race={self.race}, status='{self.status}')"

WEEKDAY_LABELS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


class RecapSettings:
    """Schedule of the weekly email listing the pending engagements an admin has to validate."""
    DEFAULT_WEEKDAY = 1  # Tuesday (Monday is 0, as in date.weekday())
    DEFAULT_HOUR = 19

    def __init__(self, enabled: bool = True, weekday: int = DEFAULT_WEEKDAY, hour: int = DEFAULT_HOUR, last_sent_on: Optional[date] = None):
        self.enabled = enabled
        self.weekday = weekday
        self.hour = hour
        self.last_sent_on = last_sent_on
