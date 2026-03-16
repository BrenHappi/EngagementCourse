from datetime import date
import re
from typing import Optional
from dataclasses import dataclass
from bcrypt import checkpw
from engagement_course.config import CATEGORY_FILTERS
import flask_login

ROLES = {
    1: "admin",
    2: "user"
}

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
        
        # Match tout ce qui est entre parenthèses
        pattern = r"(\([^\)]+\)?)"
        match = re.search(pattern, raw_category)
        if match:
            raw_category = raw_category.replace(match.group(0), "").strip()  # Remove the parenthetical part
        category_labels = CATEGORY_FILTERS.keys()
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
        parts = key.split("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return Category(level=parts[0], number=int(parts[1]))
        return None
    

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
    ):
        self.race_day = race_day
        self.date = date
        self.location = location
        self.department = department
        self.federation = federation
        self.type = type
        self.categories = categories
    
    def __repr__(self):
        return f"{self.location} ({self.date}) {self.categories}"


@dataclass(slots=True)
class RaceFilter:
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
    def __init__(self, email: str, username: str, password_hash: bytes, firstname: str, lastname: str, role: str = "user", category: Optional[Category] = None, user_id: Optional[int] = None):
        self.user_id = user_id
        self.id = user_id
        self.firstname = firstname
        self.lastname = lastname
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.category = category
        if role not in ROLES.values():
            self.role = "user"  # Default to "user"
        else:
            self.role = role

    def verify_password(self, password: str) -> bool:
        return checkpw(password.encode('utf-8'), self.password_hash)