from flask import Blueprint, render_template, current_app, abort
from flask_login import current_user, login_required

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)

    db = current_app.config["repository"]
    users = db.list_users()

    registration_url = "http://localhost:3000/register?_t=" + current_app.config['registration_token']
    return render_template(
        "admin.html",
        users=users,
        registration_url=registration_url
    )