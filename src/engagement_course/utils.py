import re
import unicodedata

from engagement_course.database import DatabaseRepository
from flask import current_app

def get_db() -> DatabaseRepository:
    return current_app.config["repository"]


def generate_username(db: DatabaseRepository, firstname: str, lastname: str) -> str:
    """Free username built from the name, e.g. "Jean", "Le Gall" -> "jlegall", then "jlegall2"..."""
    raw = (firstname[:1] + lastname).lower()
    base = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()) or "membre"
    username, suffix = base, 2
    while db.get_user_by_username(username) is not None:
        username, suffix = f"{base}{suffix}", suffix + 1
    return username
