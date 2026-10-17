from datetime import date, datetime, timedelta

from engagement_course.database import DatabaseRepository
from engagement_course.mail import send_email
from engagement_course.models import Engagement, EngagementStatus, RecapSettings, User


def upcoming_weekend(today: date) -> tuple[date, date]:
    """Saturday and Sunday of the weekend containing or following today."""
    saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    if today.weekday() == 6:
        saturday = today - timedelta(days=1)
    return saturday, saturday + timedelta(days=1)


def is_due(settings: RecapSettings, now: datetime) -> bool:
    # Any run later the same day catches up, so a missed hourly run does not skip the week
    return (
        settings.enabled
        and now.weekday() == settings.weekday
        and now.hour >= settings.hour
        and settings.last_sent_on != now.date()
    )


def pending_weekend_engagements(db: DatabaseRepository, admin: User, today: date) -> list[Engagement]:
    """Pending engagements of the admin's managed categories (all of them if none) for the coming weekend."""
    saturday, sunday = upcoming_weekend(today)
    engagements = db.list_engagements(status=EngagementStatus.PENDING.value, categories=admin.managed_categories or [])
    weekend = [e for e in engagements if saturday <= e.race.date.date() <= sunday]
    return sorted(weekend, key=lambda e: (e.race.date, e.race.location.lower(), e.user.lastname.lower(), e.user.firstname.lower()))


def format_recap(admin: User, engagements: list[Engagement], today: date, external_url: str) -> tuple[str, str]:
    saturday, sunday = upcoming_weekend(today)
    count = len(engagements)
    plural = "s" if count > 1 else ""
    subject = f"{count} inscription{plural} à valider pour le week-end du {saturday:%d/%m}"

    lines = [
        f"Bonjour {admin.firstname},",
        "",
        f"{count} inscription{plural} en attente pour le week-end du {saturday:%d/%m} au {sunday:%d/%m} :",
    ]
    current_race_id = None
    for engagement in engagements:
        race = engagement.race
        if race.id != current_race_id:
            current_race_id = race.id
            lines += ["", f"{race.race_day} {race.display_date()} · {race.location} ({race.department})"]
        category = f" ({engagement.user.category})" if engagement.user.category else ""
        lines.append(f"  - {engagement.user.firstname} {engagement.user.lastname}{category}")
    lines += [
        "",
        f"Valider : {external_url}/admin/engagements",
        f"Régler ce récap : {external_url}/profile",
    ]
    return subject, "\n".join(lines)


def send_due_recaps(db: DatabaseRepository, now: datetime, external_url: str) -> int:
    """Emails every admin whose recap is due. Returns the number of emails sent."""
    sent_count = 0
    for admin in db.list_users():
        if admin.role != "admin" or not admin.email:
            continue
        if not is_due(db.get_recap_settings(admin.user_id), now):
            continue

        engagements = pending_weekend_engagements(db, admin, now.date())
        if engagements:
            subject, message = format_recap(admin, engagements, now.date(), external_url)
            if not send_email(to_address=admin.email, subject=subject, message=message):
                continue  # Not marked as sent: the next run retries
            sent_count += 1
        db.mark_recap_sent(admin.user_id, now.date())
    return sent_count
