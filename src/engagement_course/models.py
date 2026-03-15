from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass
from bcrypt import checkpw
import secrets
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
    

class RaceEvent:
    def __init__(
        self,
        race_day: str,
        date: date,
        location: str,
        federation: str,
        type: str,
        categories: list[Category],
    ):
        self.race_day = race_day
        self.date = date
        self.location = location
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
    federation: Optional[str] = None
    type: Optional[str] = None
    category: Optional[Category] = None


class User(flask_login.UserMixin):
    def __init__(self, name: str, email: str, password_hash: bytes, role: str = "user", user_id: Optional[int] = None):
        self.id = user_id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        if role not in ROLES.values():
            self.role = "user"  # Default to "user"
        else:
            self.role = role

    def verify_password(self, password: str) -> bool:
        return checkpw(password.encode('utf-8'), self.password_hash)