from os import environ


ADMIN_EMAIL=environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD=environ.get("ADMIN_PASSWORD")
SECRET_KEY = environ.get("SECRET_KEY")

EXTERNAL_URL = environ.get("EXTERNAL_URL")

FFC_CALENDAR_URLS = {
    22: "https://www.cyclisme-amateur.com/courses-cotes-d-armor.html",
    35: "https://www.cyclisme-amateur.com/courses-ille-et-vilaine.html",
    44: "https://www.cyclisme-amateur.com/courses-loire-atlantique.html",
    53: "https://www.cyclisme-amateur.com/courses-mayenne.html",
    56: "https://www.cyclisme-amateur.com/courses-morbihan.html",   
}

SQLITE_DB_PATH = "data/sqlite.db"

DATE_FORMAT = "%d/%m/%Y"

# SMTP configuration
notify = True
SMTP_HOSTNAME = environ.get("SMTP_HOSTNAME")
SMTP_PORT = int(environ.get("SMTP_PORT", 587))
SMTP_USERNAME = environ.get("SMTP_USERNAME")
SMTP_PASSWORD = environ.get("SMTP_PASSWORD")