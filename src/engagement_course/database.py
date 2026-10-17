import secrets
import sqlite3
from bcrypt import hashpw, gensalt
from typing import Optional
from datetime import datetime
from engagement_course.config import SQLITE_DB_PATH
from engagement_course.models import CATEGORY_FREE_RACE_TYPES, merge_cyclocross_events, normalize_location, Category, RaceEvent, RaceFilter, User, Engagement


class DatabaseRepository:
    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self.db_path = db_path
        self._init_database()


    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


    def _init_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS races (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_day TEXT NOT NULL,
                    date TEXT NOT NULL,
                    location TEXT NOT NULL,
                    location_lat REAL,
                    location_lon REAL,
                    department INTEGER NOT NULL,
                    federation TEXT NOT NULL,
                    race_type TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS race_categories (
                    race_id INTEGER NOT NULL,
                    level TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    FOREIGN KEY (race_id) REFERENCES races(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_races_date ON races(date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_race_categories_race_id ON race_categories(race_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_race_categories_level_number ON race_categories(level, number)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engagements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    race_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    UNIQUE (user_id, race_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (race_id) REFERENCES races(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_engagements_status ON engagements(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_engagements_user_id ON engagements(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_engagements_race_id ON engagements(race_id)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    firstname TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    managed_categories TEXT,
                    category_key TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    address TEXT,
                    address_lat REAL,
                    address_lon REAL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            race_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(races)").fetchall()
            }
            if "location_lat" not in race_columns:
                conn.execute("ALTER TABLE races ADD COLUMN location_lat REAL")
            if "location_lon" not in race_columns:
                conn.execute("ALTER TABLE races ADD COLUMN location_lon REAL")
            if "categories_label" not in race_columns:
                conn.execute("ALTER TABLE races ADD COLUMN categories_label TEXT")

            user_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            if "address" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN address TEXT")
            if "address_lat" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN address_lat REAL")
            if "address_lon" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN address_lon REAL")

            if {"street", "city", "postal_code"}.intersection(user_columns):
                conn.execute(
                    """
                    UPDATE users
                    SET address = TRIM(
                        COALESCE(street, '')
                        || CASE
                            WHEN street IS NOT NULL AND (city IS NOT NULL OR postal_code IS NOT NULL) THEN ', '
                            ELSE ''
                        END
                        || COALESCE(postal_code, '')
                        || CASE
                            WHEN postal_code IS NOT NULL AND city IS NOT NULL THEN ' '
                            ELSE ''
                        END
                        || COALESCE(city, '')
                    )
                    WHERE address IS NULL OR address = ''
                    """
                )


    def ping(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False


    def get_registration_token(self) -> str:
        """Returns the registration token, creating it on first call (shared by all workers)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('registration_token', ?)",
                (secrets.token_urlsafe(16),),
            )
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'registration_token'"
            ).fetchone()
            return row["value"]


    def regenerate_registration_token(self) -> str:
        """Replaces the registration token, invalidating any previously shared link."""
        token = secrets.token_urlsafe(16)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('registration_token', ?)",
                (token,),
            )
        return token


    def replace_races(self, races: list[RaceEvent]) -> None:
        for race in races:
            race.location = normalize_location(race.location)
        races = merge_cyclocross_events(races)
        with self._connect() as conn:
            existing_rows = conn.execute(
                """
                SELECT id, race_day, date, location, department, federation, race_type
                FROM races
                ORDER BY id
                """
            ).fetchall()
            existing_categories: dict[int, list[str]] = {}
            for row in conn.execute("SELECT race_id, level, number FROM race_categories"):
                existing_categories.setdefault(int(row["race_id"]), []).append(f"{row['level']}_{row['number']}")
            # Several races can share a key (e.g. OPEN and ACCESS races of the same event): keep all ids,
            # each imported race reuses one of them, the leftovers are stale
            existing_by_key: dict[tuple, list[int]] = {}
            for row in existing_rows:
                key = (
                    row["race_day"],
                    row["date"],
                    normalize_location(row["location"]),  # rows stored before locations were normalized
                    int(row["department"]),
                    row["federation"],
                    row["race_type"],
                    tuple(sorted(existing_categories.get(int(row["id"]), []))),
                )
                existing_by_key.setdefault(key, []).append(int(row["id"]))

            for race in races:
                if not race.is_relevant():
                    continue

                race_date = race.date.strftime("%Y-%m-%d")
                stored_categories = (race.categories or []) if race.requires_category_match else []
                race_key = (
                    race.race_day,
                    race_date,
                    race.location,
                    int(race.department),
                    race.federation,
                    race.type,
                    tuple(sorted(category.to_key() for category in stored_categories)),
                )

                if existing_by_key.get(race_key):
                    race_id = existing_by_key[race_key].pop(0)
                    conn.execute(
                        """
                        UPDATE races
                        SET location = ?, location_lat = ?, location_lon = ?, categories_label = ?
                        WHERE id = ?
                        """,
                        (race.location, race.location_lat, race.location_lon, race.categories_label, race_id),
                    )
                else:
                    cursor = conn.execute(
                        """
                        INSERT INTO races (race_day, date, location, location_lat, location_lon, department, federation, race_type, categories_label)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            race.race_day,
                            race_date,
                            race.location,
                            race.location_lat,
                            race.location_lon,
                            race.department,
                            race.federation,
                            race.type,
                            race.categories_label,
                        ),
                    )
                    race_id = int(cursor.lastrowid)

                conn.execute("DELETE FROM race_categories WHERE race_id = ?", (race_id,))

                category_records = [
                    (race_id, category.level, category.number)
                    for category in stored_categories
                ]
                if category_records:
                    conn.executemany(
                        """
                        INSERT INTO race_categories (race_id, level, number)
                        VALUES (?, ?, ?)
                        """,
                        category_records,
                    )

            stale_race_ids = [race_id for race_ids in existing_by_key.values() for race_id in race_ids]
            for race_id in stale_race_ids:
                has_engagement = conn.execute(
                    "SELECT 1 FROM engagements WHERE race_id = ? LIMIT 1",
                    (race_id,),
                ).fetchone()
                if has_engagement:
                    continue
                conn.execute("DELETE FROM races WHERE id = ?", (race_id,))


    def get_race_by_id(self, race_id:int) -> RaceEvent | None:
        """
        Returns a RaceEvent object matching the given id, or None if not found.
        """
        races = self.search_races(RaceFilter(id=race_id))
        if len(races) > 1:
            raise ValueError(f"Multiple races found with id {race_id}")
        return races[0] if races else None


    def list_races(self) -> list[RaceEvent]:
        return self.search_races()


    def list_races_by_category(self, category: Category) -> list[RaceEvent]:
        filters = RaceFilter(category=[category])
        return self.search_races(filters)


    def search_races(self, filters: RaceFilter | None = None) -> list[RaceEvent]:
        f = filters or RaceFilter()
        where = []
        params = []

        if f.id:
            where.append("r.id = ?")
            params.append(f.id)

        if f.date_from:
            where.append("r.date >= ?")
            params.append(f.date_from)

        if f.date_to:
            where.append("r.date <= ?")
            params.append(f.date_to)

        if f.location:
            where.append("r.location = ?")
            params.append(f.location)
        
        if f.department:
            placeholders = ", ".join("?" * len(f.department))
            where.append(f"r.department IN ({placeholders})")
            params.extend(f.department)

        if f.federation:
            where.append("r.federation = ?")
            params.append(f.federation)

        if f.type:
            where.append("r.race_type = ?")
            params.append(f.type)

        if f.category:
            cat_conditions = []
            for cat in f.category:
                cat_conditions.append(
                    """
                    EXISTS (
                        SELECT 1 FROM race_categories AS rc
                        WHERE rc.race_id = r.id
                        AND rc.level = ?
                        AND rc.number = ?
                    )
                    """
                )
                params.append(cat.level)
                params.append(cat.number)
            # Cyclo-cross age-group races (no OPEN/ACCESS categories) are open to every rider
            cat_conditions.append(
                f"(r.race_type IN ({', '.join('?' * len(CATEGORY_FREE_RACE_TYPES))})"
                " AND NOT EXISTS (SELECT 1 FROM race_categories AS rc WHERE rc.race_id = r.id))"
            )
            params.extend(CATEGORY_FREE_RACE_TYPES)
            where.append("(" + " OR ".join(cat_conditions) + ")")

        query = f"""
        SELECT
            r.id,
            r.race_day,
            r.date,
            r.location,
            r.location_lat,
            r.location_lon,
            r.department,
            r.federation,
            r.race_type,
            r.categories_label,
            rc.level AS category_level,
            rc.number AS category_number
            FROM races as r
            LEFT JOIN race_categories AS rc ON rc.race_id = r.id
        """

        if where:
            query += " WHERE " + " AND ".join(where)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        races_by_id: dict[int, RaceEvent] = {}

        for row in rows:
            race_id = int(row["id"])
            race = races_by_id.get(race_id)
            if race is None:
                race = RaceEvent(
                    id=race_id,
                    race_day=row["race_day"],
                    date=datetime.strptime(row["date"], "%Y-%m-%d"),
                    location=row["location"],
                    location_lat=row["location_lat"],
                    location_lon=row["location_lon"],
                    department=row["department"],
                    federation=row["federation"],
                    type=row["race_type"],
                    categories=[],
                    categories_label=row["categories_label"],
                )
                races_by_id[race_id] = race

            if row["category_level"] is not None:
                race.categories.append(
                    Category(
                        level=row["category_level"],
                        number=int(row["category_number"]),
                    )
                )

        return list(races_by_id.values())


    def create_engagement(self, user_id: int, race: RaceEvent, status: str) -> int | None:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO engagements (user_id, race_id, status)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, race.id, status)
                )
                return int(cursor.lastrowid)
            
        except sqlite3.IntegrityError as e:
            raise ValueError("Un engagement existe déjà pour cet utilisateur et cette course") from e


    def update_engagement(self, engagement_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE engagements
                SET status = ?
                WHERE id = ?
                """,
                (status, engagement_id)
            )


    def delete_engagement(self, engagement_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM engagements WHERE id = ?",
                (engagement_id,)
            )


    def get_engagement_by_id(self, engagement_id: int) -> Engagement | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, race_id, status
                FROM engagements
                WHERE id = ?
                """,
                (engagement_id,),
            ).fetchone()

        if row is None:
            return None

        return Engagement(
            id=row["id"],
            user=self.get_user_by_id(row["user_id"]),
            race=self.get_race_by_id(row["race_id"]),
            status=row["status"],
        )


    def list_engagements(self, user_id: Optional[int] = None, status: Optional[str] = None, categories: Optional[list[Category]] = None) -> list[Engagement]:
        """
        Returns a list of engagements, optionally filtered by status.
        If status is None, returns all engagements.
        
        Arguments:
        - user_id: optional filter to return only engagements for a specific user
        - status: optional filter to return only engagements with a specific status (e.g., "pending", "validated", "interested")
        - categories: optional filter to return only engagements with specific categories
        Returns: a list of Engagement objects matching the criteria
        """
        engagements = []
        with self._connect() as conn:
            query = "SELECT e.id, e.user_id, e.race_id, e.status FROM engagements AS e"
            where_clauses = []
            params = []

            if user_id is not None:
                where_clauses.append("e.user_id = ?")
                params.append(user_id)

            if status is not None:
                where_clauses.append("e.status = ?")
                params.append(status)

            if categories is not None and len(categories) > 0:
                category_filters = []
                for cat in categories:
                    if cat is None:
                        continue
                    category_filters.append("(rc.level = ? AND rc.number = ?)")
                    params.append(cat.level)
                    params.append(cat.number)

                if category_filters:
                    # Races without OPEN/ACCESS categories (cyclo-cross): match on the rider category instead
                    category_keys = [cat.to_key() for cat in categories if cat is not None]
                    params.extend(CATEGORY_FREE_RACE_TYPES)
                    params.extend(category_keys)
                    where_clauses.append(
                        """
                        (EXISTS (
                            SELECT 1 FROM race_categories AS rc
                            WHERE rc.race_id = e.race_id
                            AND (
                                """
                        + " OR ".join(category_filters)
                        +
                        f"""
                            )
                        )
                        OR (
                            EXISTS (SELECT 1 FROM races AS r WHERE r.id = e.race_id AND r.race_type IN ({', '.join('?' * len(CATEGORY_FREE_RACE_TYPES))}))
                            AND NOT EXISTS (SELECT 1 FROM race_categories AS rc WHERE rc.race_id = e.race_id)
                            AND EXISTS (SELECT 1 FROM users AS u WHERE u.id = e.user_id AND u.category_key IN ({', '.join('?' * len(category_keys))}))
                        ))
                        """
                    )

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            rows = conn.execute(query, params).fetchall()
        
        for row in rows:
            engagements.append(
                Engagement(
                    id=row["id"],
                    user=self.get_user_by_id(row["user_id"]),
                    race=self.get_race_by_id(row["race_id"]),
                    status=row["status"],
                )
            )
        return engagements


    def list_user_engagements(self, user: Optional[User]) -> list[Engagement]:
        """
        Returns a list of engagements for a given user.
        If none is provided, returns current user's engagements.

        Arguments:
        - user: target user
        Returns: a list of Engagement objects matching the criteria
        """
        if user is None:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, race_id, status FROM engagements
                WHERE user_id = ?
                """,
                (user.user_id,)
            ).fetchall()

        engagements = []
        for row in rows:
            engagements.append(
                Engagement(
                    id=row["id"],
                    user=user,
                    race=self.get_race_by_id(row["race_id"]),
                    status=row["status"],
                )
            )
        return list(engagements)
    

    def list_race_engagements(self, race_id: int, status: Optional[str] = None) -> list[Engagement]:
        """
        Returns a list of engagements for a given race

        Arguments:
        - race_id: target race
        - status: optional filter to return only engagements with a specific status (e.g., "validated", "pending", "interested")
        Returns: a list of Engagement objects matching the criteria
        """
        engagements = []
        with self._connect() as conn:
            query = """
                SELECT id, user_id, race_id, status FROM engagements
                WHERE race_id = ?
            """
            params = [race_id]
            if status is not None:
                query += " AND status = ?"
                params.append(status)
            rows = conn.execute(query, params).fetchall()

        for row in rows:
            engagements.append(
                Engagement(
                    id=row["id"],
                    user=self.get_user_by_id(row["user_id"]),
                    race=self.get_race_by_id(row["race_id"]),
                    status=row["status"],
                )
            )
        return engagements


    def create_user(self, email: str, username: str, password: str, firstname: str, lastname: str, role: str = "user", category: Optional[Category] = None, managed_categories: Optional[list[Category]] = None, address: Optional[str] = None) -> int:
        category_key = category.to_key() if category is not None else None
        managed_categories_keys = ",".join([c.to_key() for c in managed_categories]) if managed_categories is not None else None

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (email, username, hashpw(password.encode('utf-8'), gensalt()), category_key, managed_categories_keys, firstname, lastname, role, address, None, None),
            )
            return int(cursor.lastrowid)
        

    def update_user(self, user_id: int, email: Optional[str]=None, username: Optional[str]=None, password: Optional[str]=None, firstname: Optional[str]=None, lastname: Optional[str]=None, role: Optional[str]=None, category: Optional[Category]=None, managed_categories: Optional[list[Category]] = None, address: Optional[str]=None) -> None:
        category_key = category.to_key() if category is not None else None
        managed_categories_keys = ",".join([c.to_key() for c in managed_categories]) if managed_categories is not None else None
        with self._connect() as conn:
            user = self.get_user_by_id(user_id)
            if user is None:
                raise ValueError("User not found")


            updated_email = email if email is not None else user.email
            updated_username = username if username is not None else user.username
            updated_password_hash = hashpw(password.encode('utf-8'), gensalt()) if password is not None else user.password_hash
            updated_firstname = firstname if firstname is not None else user.firstname
            updated_lastname = lastname if lastname is not None else user.lastname
            updated_role = role if role is not None else user.role
            updated_category_key = category_key if category_key is not None else (user.category.to_key() if user.category else None)
            updated_managed_categories_keys = managed_categories_keys if managed_categories_keys is not None else (",".join([c.to_key() for c in user.managed_categories]) if user.managed_categories else None)
            updated_address = address if address is not None else user.address
            address_changed = updated_address != user.address
            updated_address_lat = None if address_changed else user.address_lat
            updated_address_lon = None if address_changed else user.address_lon

            conn.execute(
                """
                UPDATE users
                SET email = ?, username = ?, password = ?, category_key = ?, managed_categories = ?, firstname = ?, lastname = ?, role = ?, address = ?, address_lat = ?, address_lon = ?
                WHERE id = ?
                """,
                (updated_email, updated_username, updated_password_hash, updated_category_key, updated_managed_categories_keys, updated_firstname, updated_lastname, updated_role, updated_address, updated_address_lat, updated_address_lon, user_id),
            )


    def update_user_coordinates(self, user_id: int, address_lat: Optional[float], address_lon: Optional[float]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET address_lat = ?, address_lon = ?
                WHERE id = ?
                """,
                (address_lat, address_lon, user_id),
            )


    def update_race_coordinates(self, race_id: int, location_lat: Optional[float], location_lon: Optional[float]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE races
                SET location_lat = ?, location_lon = ?
                WHERE id = ?
                """,
                (location_lat, location_lon, race_id),
            )


    def delete_user(self, user_id: int) -> None:
        with self._connect() as conn:
            user = self.get_user_by_id(user_id)
            if user is None:
                raise ValueError("User not found")
            conn.execute(
                "DELETE FROM users WHERE id = ?",
                (user_id,)
            )


    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon
                FROM users
                ORDER BY id
                """
            ).fetchall()

        return [
            User(
                user_id=row["id"],
                email=row["email"],
                username=row["username"],
                password_hash=row["password"],
                category=Category.from_key(row["category_key"]) if row["category_key"] else None,
                firstname=row["firstname"],
                lastname=row["lastname"],
                role=row["role"],
                address=row["address"],
                address_lat=row["address_lat"],
                address_lon=row["address_lon"],
            )

            for row in rows
        ]
    

    def get_user_by_id(self, id: int) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon
                FROM users
                WHERE id = ?
                """,
                (id,)
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row["id"],
            email=row["email"],
            username=row["username"],
            password_hash=row["password"],
            category=Category.from_key(row["category_key"]) if row["category_key"] else None,
            managed_categories=[Category.from_key(key) for key in row["managed_categories"].split(",")] if row["managed_categories"] else None,
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
            address=row["address"],
            address_lat=row["address_lat"],
            address_lon=row["address_lon"]
        )
    

    def get_user_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row["id"],
            email=row["email"],
            username=row["username"],
            password_hash=row["password"],
            category=Category.from_key(row["category_key"]) if row["category_key"] else None,
            managed_categories=[Category.from_key(key) for key in row["managed_categories"].split(",")] if row["managed_categories"] else None,
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
            address=row["address"],
            address_lat=row["address_lat"],
            address_lon=row["address_lon"]
        )
    

    def get_user_by_username(self, username: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon
                FROM users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row["id"],
            email=row["email"],
            username=row["username"],
            password_hash=row["password"],
            category=Category.from_key(row["category_key"]) if row["category_key"] else None,
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
            managed_categories=[Category.from_key(key) for key in row["managed_categories"].split(",")] if row["managed_categories"] else None,
            address=row["address"],
            address_lat=row["address_lat"],
            address_lon=row["address_lon"]
        )


    def get_manager_for_category(self, category: Category) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, managed_categories, firstname, lastname, role, address, address_lat, address_lon
                FROM users
                WHERE role = 'admin' AND managed_categories LIKE ?
                """,
                (f"%{category.to_key()}%",)
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row["id"],
            email=row["email"],
            username=row["username"],
            password_hash=row["password"],
            category=Category.from_key(row["category_key"]) if row["category_key"] else None,
            managed_categories=[Category.from_key(key) for key in row["managed_categories"].split(",")] if row["managed_categories"] else None,
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
            address=row["address"],
            address_lat=row["address_lat"],
            address_lon=row["address_lon"]
        )