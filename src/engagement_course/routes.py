from flask import Blueprint, render_template, current_app, request, abort
from flask_login import current_user, login_required
from datetime import datetime
from engagement_course.models import RaceFilter, Category
from engagement_course.config import FFC_CALENDAR_URLS, DATE_FORMAT, CATEGORY_FILTERS

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
    categories = [c for c in (Category.from_key(k) for k in raw_categories) if c] or None

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
        available_category_filters=CATEGORY_FILTERS,
    )

@main_bp.route("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)
    db = current_app.config["repository"]
    users = db.list_users()
    return render_template("admin.html", users=users)
    