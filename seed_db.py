#!/usr/bin/env python3
"""
Script de seed: remplit la base de données avec des données de test.
Usage: python seed_db.py
"""

from datetime import timedelta, date
from src.engagement_course.database import DatabaseRepository
from src.engagement_course.models import Category, RaceEvent, EngagementStatus

def seed_database():
    db = DatabaseRepository()
    
    # Créer quelques utilisateurs
    print("Création des utilisateurs...")
    
    # Admin
    admin_id = db.create_user(
        email="admin@test.fr",
        username="test_admin",
        password="admin123",
        firstname="Admin",
        lastname="Test",
        role="admin"
    )
    print(f"✓ Admin créé (ID: {admin_id})")
    
    # Users normaux
    users = []
    user_data = [
        ("alice@test.fr", "alice", "Alice", "Dupont", Category("ACCESS", 1)),
        ("bob@test.fr", "bob", "Bob", "Martin", Category("ACCESS", 2)),
        ("charlie@test.fr", "charlie", "Charlie", "Bernard", Category("ACCESS", 3)),
        ("diana@test.fr", "diana", "Diana", "Lefevre", Category("ACCESS", 4)),
    ]
    
    for email, username, firstname, lastname, category in user_data:
        user_id = db.create_user(
            email=email,
            username=username,
            password=username,
            firstname=firstname,
            lastname=lastname,
            role="user",
            category=category
        )
        users.append(user_id)
        print(f"✓ User créé: {firstname} {lastname} - {category} (ID: {user_id})")
    
    # Créer quelques courses de test
    print("\nCréation des courses...")
    
    today = date.today()
    races = []
    
    race_data = [
        ("Circuit du dimanche", today + timedelta(days=7), "Rennes", 35, "FFC", [Category("ACCESS", 1)]),
        ("Contre-la-montre", today + timedelta(days=14), "Saint-Malo", 35, "FFC", [Category("ACCESS", 1), Category("ACCESS", 3)]),
        ("Route côtière", today + timedelta(days=21), "Lorient", 56, "FFC", [Category("ACCESS", 1), Category("ACCESS", 2), Category("ACCESS", 3), Category("ACCESS", 4)]),
        ("Classique printanière", today + timedelta(days=28), "Nantes", 44, "FFC", [Category("ACCESS", 1), Category("ACCESS", 2), Category("ACCESS", 3)]),
    ]
    
    for race_day, race_date, location, dept, federation, categories in race_data:
        race = RaceEvent(
            race_day=race_day,
            date=race_date,
            location=location,
            department=dept,
            federation=federation,
            type="ROUTE",
            categories=categories
        )
        races.append(race)
    
    
    # Utiliser replace_races pour insérer les courses (remplace les existing)
    db.replace_races(races)
    print(f"✓ {len(races)} courses créées")
    
    # Créer les engagements
    print("\nCréation des engagements...")
    
    # Récupérer les courses depuis la DB
    db_races = db.list_races()
    
    engagement_count = 0
    statuses = [EngagementStatus.INTERESTED, EngagementStatus.PENDING, EngagementStatus.VALIDATED]
    
    for idx, user_id in enumerate(users):
        for race_idx, race in enumerate(db_races):
            # Créer un engagement pour certaines combinaisons
            if (idx + race_idx) % 3 != 0:  # Créer engagements de manière variable
                status = statuses[(idx + race_idx) % len(statuses)]
                try:
                    db.create_engagement(user_id, race, status)
                    engagement_count += 1
                except ValueError as e:
                    # Engagement déjà existant, c'est normal
                    pass
    
    print(f"✓ {engagement_count} engagements créés")
    
    # Résumé
    print("\n" + "="*50)
    print("SEED COMPLÉTÉ ✓")
    print("="*50)
    print(f"Users: {len(users) + 1} (admin + {len(users)} normaux)")
    print(f"Courses: {len(db_races)}")
    print(f"Engagements: {engagement_count}")
    print("\nCredentials de test:")
    print("  - Admin: admin / admin123")
    print("  - Alice: alice@test.fr / password123")
    print("  - Bob: bob@test.fr / password123")
    print("  - Charlie: charlie@test.fr / password123")
    print("  - Diana: diana@test.fr / password123")

if __name__ == "__main__":
    seed_database()
