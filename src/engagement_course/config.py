from os import environ


ADMIN_EMAIL=environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD=environ.get("ADMIN_PASSWORD")
SECRET_KEY = environ.get("SECRET_KEY")

LOG_LEVEL = (environ.get("LOG_LEVEL") or "INFO").upper()

EXTERNAL_URL = (environ.get("EXTERNAL_URL") or "").rstrip("/") or None

FFC_CALENDAR_URLS = {
    22: "https://www.cyclisme-amateur.com/courses-cotes-d-armor.html",
    35: "https://www.cyclisme-amateur.com/courses-ille-et-vilaine.html",
    44: "https://www.cyclisme-amateur.com/courses-loire-atlantique.html",
    53: "https://www.cyclisme-amateur.com/courses-mayenne.html",
    56: "https://www.cyclisme-amateur.com/courses-morbihan.html",   
}

DEPARTMENT_NAMES = {
    22: "Côtes-d'Armor",
    35: "Ille-et-Vilaine",
    44: "Loire-Atlantique",
    53: "Mayenne",
    56: "Morbihan",
}

# Riders can ask for an engagement until this many days before the race
ENGAGEMENT_CLOSING_DAYS = 5

SQLITE_DB_PATH = "data/sqlite.db"

DATE_FORMAT = "%d/%m/%Y"

# Admin recap emails are scheduled in club local time, whatever the server timezone
TIMEZONE = "Europe/Paris"

PASSWORD_RESET_MAX_AGE = 3600  # seconds
PASSWORD_MIN_LENGTH = 8

# SMTP configuration
SMTP_HOSTNAME = environ.get("SMTP_HOSTNAME")
SMTP_PORT = int(environ.get("SMTP_PORT") or 587)
SMTP_USERNAME = environ.get("SMTP_USERNAME")
SMTP_PASSWORD = environ.get("SMTP_PASSWORD")
SMTP_TIMEOUT = 10  # seconds
# Email notifications are only sent when SMTP is fully configured
notify = all([SMTP_HOSTNAME, SMTP_USERNAME, SMTP_PASSWORD])

REQUIRED_SETTINGS = ("SECRET_KEY", "EXTERNAL_URL")


def validate() -> None:
    """Fails fast at startup instead of running with a broken or insecure configuration."""
    missing = [name for name in REQUIRED_SETTINGS if not globals()[name]]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")