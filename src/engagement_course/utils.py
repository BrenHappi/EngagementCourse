import re
import unicodedata

from engagement_course.config import PASSWORD_MIN_LENGTH
from engagement_course.database import DatabaseRepository
from flask import current_app

def get_db() -> DatabaseRepository:
    return current_app.config["repository"]


def password_problem(password: str) -> str | None:
    """Reason why a new password is refused, None when it is acceptable."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit faire au moins {PASSWORD_MIN_LENGTH} caractères"
    return None


def generate_username(db: DatabaseRepository, firstname: str, lastname: str) -> str:
    """Free username built from the name, e.g. "Jean", "Le Gall" -> "jlegall", then "jlegall2"..."""
    raw = (firstname[:1] + lastname).lower()
    base = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()) or "membre"
    username, suffix = base, 2
    while db.get_user_by_username(username) is not None:
        username, suffix = f"{base}{suffix}", suffix + 1
    return username
