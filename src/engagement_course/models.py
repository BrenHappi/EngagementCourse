from datetime import date
from enum import Enum
import re
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