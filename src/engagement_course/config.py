import secrets

ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="admin"
SECRET_KEY = "121c4bcdfa653bb27efdd69fb41681b5"

FFC_CALENDAR_URLS = {
    22: "https://www.cyclisme-amateur.com/courses-cotes-d-armor.html",
    35: "https://www.cyclisme-amateur.com/courses-ille-et-vilaine.html",
    44: "https://www.cyclisme-amateur.com/courses-loire-atlantique.html",
    53: "https://www.cyclisme-amateur.com/courses-mayenne.html",
    56: "https://www.cyclisme-amateur.com/courses-morbihan.html",   
}

SQLITE_DB_PATH = "sqlite.db"

REGISTRATION_TOKEN = secrets.token_hex(16)  # V2 -> uses something that can be revoked and regenerated

DATE_FORMAT = "%d/%m/%Y"

# # Available category filters for the search form.
# CATEGORY_FILTERS = {
#     "OPEN": [1, 2, 3],
#     "ACCESS": [1, 2, 3, 4],
# }