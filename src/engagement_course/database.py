import sqlite3
from bcrypt import hashpw, gensalt
from typing import Optional
from datetime import datetime
from engagement_course.config import SQLITE_DB_PATH, DATE_FORMAT
from engagement_course.models import Category, RaceEvent, RaceFilter, User


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
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    firstname TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    category_key TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
            )


    def replace_races(self, races: list[RaceEvent]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM races")
            for race in races:
                if race.type != "ROUTE":
                    continue    # only store "ROUTE" races
                if not race.categories:
                    continue    # skip races without categories
                cursor = conn.execute(
                    """
                    INSERT INTO races (race_day, date, location, department, federation, race_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        race.race_day,
                        race.date,
                        race.location,
                        race.department,
                        race.federation,
                        race.type,
                    ),
                )
                race_id = int(cursor.lastrowid)

                category_records = [
                    (race_id, category.level, category.number)
                    for category in race.categories
                ]
                if category_records:
                    conn.executemany(
                        """
                        INSERT INTO race_categories (race_id, level, number)
                        VALUES (?, ?, ?)
                        """,
                        category_records,
                    )


    def list_races(self) -> list[RaceEvent]:
        return self.search_races()


    def list_races_by_category(self, category: Category) -> list[RaceEvent]:
        filters = RaceFilter(category=[category])
        return self.search_races(filters)


    def search_races(self, filters: RaceFilter | None = None) -> list[RaceEvent]:
        f = filters or RaceFilter()
        where = []
        params = []

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
            where.append("(" + " OR ".join(cat_conditions) + ")")

        query = f"""
        SELECT
            r.id,
            r.race_day,
            r.date,
            r.location,
            r.department,
            r.federation,
            r.race_type,
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
                    race_day=row["race_day"],
                    date=datetime.strptime(row["date"], "%Y-%m-%d"),
                    location=row["location"],
                    department=row["department"],
                    federation=row["federation"],
                    type=row["race_type"],
                    categories=[],
                )
                races_by_id[race_id] = race

            if row["category_level"] is not None:
                race.categories.append(
                    Category(
                        level=row["category_level"],
                        number=int(row["category_number"]),
                    )
                )

        return races_by_id.values()


    def create_user(self, email: str, username: str, password: str, firstname: str, lastname: str, role: str = "user", category: Optional[Category] = None) -> int:
        category_key = f"{category.level}_{category.number}" if category is not None else None
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, username, password, category_key, firstname, lastname, role)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (email, username, hashpw(password.encode('utf-8'), gensalt()), category_key, firstname, lastname, role),
            )
            return int(cursor.lastrowid)
        

    def update_user(self, user_id: int, email: Optional[str]=None, username: Optional[str]=None, password: Optional[str]=None, firstname: Optional[str]=None, lastname: Optional[str]=None, role: Optional[str]=None, category: Optional[Category]=None) -> None:
        category_key = f"{category.level}_{category.number}" if category is not None else None
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

            conn.execute(
                """
                UPDATE users
                SET email = ?, username = ?, password = ?, category_key = ?, firstname = ?, lastname = ?, role = ?
                WHERE id = ?
                """,
                (updated_email, updated_username, updated_password_hash, updated_category_key, updated_firstname, updated_lastname, updated_role, user_id),
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
                SELECT id, email, username, password, category_key, firstname, lastname, role
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
            )

            for row in rows
        ]
    

    def get_user_by_id(self, id: int) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, firstname, lastname, role
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
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
        )
    

    def get_user_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, firstname, lastname, role
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
            firstname=row["firstname"],
            lastname=row["lastname"],
            role=row["role"],
        )
    

    def get_user_by_username(self, username: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, email, username, password, category_key, firstname, lastname, role
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
        )