from flask import Blueprint, render_template, current_app, request, abort
from flask_login import current_user, login_required
from datetime import datetime
from engagement_course.models import RaceFilter, Category, CATEGORIES
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
@login_required
def index():
    now = datetime.now()
    now_display = now.strftime(DATE_FORMAT)
    date_from = datetime.strptime(request.args.get("date_from"), DATE_FORMAT) if request.args.get("date_from") else now
    date_to = datetime.strptime(request.args.get("date_to"), DATE_FORMAT) if request.args.get("date_to") else None

    raw_departments = [d for d in request.args.getlist("department") if d.isdigit()]
    departments = [int(d) for d in raw_departments] or None

    raw_categories = request.args.getlist("category")
    parsed_categories = [c for c in (Category.from_key(k) for k in raw_categories) if c]

    if parsed_categories:
        categories = parsed_categories
        selected_category_keys = [category.to_key() for category in parsed_categories]
    elif current_user.category is not None:
        categories = [current_user.category]
        selected_category_keys = [current_user.category.to_key()]
    else:
        categories = None
        selected_category_keys = []

    filters = RaceFilter(
            date_from=date_from,
            date_to=date_to,
            location=request.args.get("location"),
            department=departments,
            federation=request.args.get("federation"),
            type=request.args.get("type"),
            category=categories,
    )
    db = current_app.config["repository"]
    races = db.search_races(filters)
    # Temporary storing date in string fmt for display purposes. Should ideally be handled in template or via a view model.
    for race in races:
        race.date = race.date.strftime(DATE_FORMAT)
    return render_template(
        "home.html",
        username=current_user.username if current_user.is_authenticated else None,
        races=races,
        now=now_display,
        available_departments=FFC_CALENDAR_URLS.keys(),
        available_category_filters=CATEGORIES,
        selected_category_keys=selected_category_keys,
    )
    