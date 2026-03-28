from engagement_course.database import DatabaseRepository
from flask import current_app

def get_db() -> DatabaseRepository:
    return current_app.config["repository"]