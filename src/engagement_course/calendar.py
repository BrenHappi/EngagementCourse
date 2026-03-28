from flask import Blueprint, render_template, current_app, request, abort, redirect, url_for, flash
from flask_login import current_user, login_required
from datetime import datetime
from engagement_course.models import RaceFilter, Category, CATEGORIES
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT
from engagement_course.utils import get_db


calendar_bp = Blueprint("calendar", __name__)

@calendar_bp.route("/")
@login_required
def index():
    now = datetime.now()
    now_display = now.strftime(DATE_FORMAT)
    reset_filters = request.args.get("reset") == "1"
    category_filter_submitted = request.args.get("category_filter_submitted") == "1"
    date_from = datetime.strptime(request.args.get("date_from"), DATE_FORMAT) if request.args.get("date_from") else now
    date_to = datetime.strptime(request.args.get("date_to"), DATE_FORMAT) if request.args.get("date_to") else None

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
    for race in races:
        race.my_engagement_id = None
        race.engagements = db.list_race_engagements(race.id)
        for engagement in race.engagements:
            if engagement.user == current_user:
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
            
    return render_template(
        "home.html",
        username=current_user.username if current_user.is_authenticated else None,
        races=races,
        now=now_display,
        available_departments=FFC_CALENDAR_URLS.keys(),
        available_category_filters=CATEGORIES,
        selected_category_keys=selected_category_keys,
        category_filter_mode=category_filter_mode,
    )
