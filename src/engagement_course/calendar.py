from flask import Blueprint, render_template, current_app, request, abort, redirect, url_for, flash
from flask_login import current_user, login_required
from datetime import datetime, date
import calendar as cal_module
from engagement_course.models import RaceFilter, Category, CATEGORIES
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT
from engagement_course.utils import get_db

MONTH_NAMES_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

calendar_bp = Blueprint("calendar", __name__)

@calendar_bp.route("/")
@login_required
def index():
    now = datetime.now()
    reset_filters = request.args.get("reset") == "1"
    category_filter_submitted = request.args.get("category_filter_submitted") == "1"
    show_my_engagements = request.args.get("my_engagements") == "1"
    show_past_races = request.args.get("show_past") == "1"

    try:
        current_month = int(request.args.get("month", now.month))
        current_year = int(request.args.get("year", now.year))
        if not (1 <= current_month <= 12):
            raise ValueError
    except (ValueError, TypeError):
        current_month = now.month
        current_year = now.year

    _, last_day = cal_module.monthrange(current_year, current_month)
    date_from = datetime(current_year, current_month, 1)
    date_to = datetime(current_year, current_month, last_day)

    prev_month = current_month - 1 if current_month > 1 else 12
    prev_year = current_year if current_month > 1 else current_year - 1
    next_month = current_month + 1 if current_month < 12 else 1
    next_year = current_year if current_month < 12 else current_year + 1

    raw_departments = [d for d in request.args.getlist("department") if d.isdigit()]
    departments = [int(d) for d in raw_departments] or None

    raw_categories = request.args.getlist("category")
    parsed_categories: list[Category] = [c for c in (Category.from_key(k) for k in raw_categories) if c]

    if parsed_categories:
        categories = parsed_categories
        selected_category_keys = [category.to_key() for category in parsed_categories]
        category_filter_mode = "explicit"
    elif reset_filters or category_filter_submitted:
        categories = None
        selected_category_keys = []
        category_filter_mode = "none"
    else:
        categories = [current_user.category] if current_user.category else None
        selected_category_keys = [current_user.category.to_key()] if current_user.category else []
        category_filter_mode = "default" if current_user.category else "none"

    # Build base query params (without month/year) to preserve filters in prev/next links
    filter_params = []
    for d in (raw_departments or []):
        filter_params.append(f"department={d}")
    for k in (raw_categories or []):
        filter_params.append(f"category={k}")
    if show_my_engagements:
        filter_params.append("my_engagements=1")
    if show_past_races:
        filter_params.append("show_past=1")
    if category_filter_submitted:
        filter_params.append("category_filter_submitted=1")
    filter_qs = ("&" + "&".join(filter_params)) if filter_params else ""

    prev_url = url_for("calendar.index") + f"?month={prev_month}&year={prev_year}" + filter_qs
    next_url = url_for("calendar.index") + f"?month={next_month}&year={next_year}" + filter_qs

    filters = RaceFilter(
            date_from=date_from,
            date_to=date_to,
            location=request.args.get("location"),
            department=departments,
            federation=request.args.get("federation"),
            type=request.args.get("type"),
            category=categories,
    )
    db = get_db()
    races = db.search_races(filters)
    filtered_races = []
    today = date.today()
    for race in races:
        race.my_engagement_id = None
        race.my_status = "none"
        race.engagements = db.list_race_engagements(race.id)
        for engagement in race.engagements:
            if engagement.user and engagement.user.user_id == current_user.user_id:
                race.my_status = engagement.status
                race.my_engagement_id = engagement.id
            match engagement.status:
                case "validated":
                    if engagement.user not in race.validated_users:
                        race.validated_users.append(engagement.user)
                case "pending":
                    if engagement.user not in race.pending_users:
                        race.pending_users.append(engagement.user)
                case "interested":
                    if engagement.user not in race.interested_users:
                        race.interested_users.append(engagement.user)

        if not show_past_races and race.date.date() < today:
            continue
        if show_my_engagements and race.my_status not in {"interested", "pending", "validated"}:
            continue
        filtered_races.append(race)

    races = filtered_races

    month_label = f"{MONTH_NAMES_FR[current_month]} {current_year}"

    return render_template(
        "home.html",
        username=current_user.username if current_user.is_authenticated else None,
        races=races,
        now=now.strftime(DATE_FORMAT),
        available_departments=FFC_CALENDAR_URLS.keys(),
        available_category_filters=CATEGORIES,
        selected_category_keys=selected_category_keys,
        category_filter_mode=category_filter_mode,
        show_my_engagements=show_my_engagements,
        show_past_races=show_past_races,
        current_month=current_month,
        current_year=current_year,
        month_label=month_label,
        prev_url=prev_url,
        next_url=next_url,
    )
