import secrets

FFC_CALENDAR_URL = "https://www.cyclisme-amateur.com/courses-ille-et-vilaine.html"
SQLITE_DB_PATH = "sqlite.db"
REGISTRATION_TOKEN = secrets.token_hex(16)  # V2 -> uses something that can be revoked and regenerated