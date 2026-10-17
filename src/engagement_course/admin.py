from flask import Blueprint, render_template, current_app, abort, request, flash, redirect, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, SelectField, SelectMultipleField, StringField
from wtforms.validators import DataRequired, Optional
from engagement_course.mail import send_email
from engagement_course.utils import generate_username, get_db
from engagement_course.models import CATEGORIES, Category, EngagementStatus

admin_bp = Blueprint("admin", __name__)

class AdminCreateUserForm(FlaskForm):
    firstname = StringField(validators=[DataRequired()])
    lastname = StringField(validators=[DataRequired()])
    username = StringField(validators=[Optional()])
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])
    address = StringField(validators=[Optional()])
    category = SelectField(validators=[Optional()])
    role = SelectField(choices=[("user", "User"), ("admin", "Admin")], validators=[DataRequired()])
    managed_categories = SelectMultipleField(choices=Category.get_category_options(), validators=[Optional()])

class AdminUpdateUserForm(FlaskForm):
    user_id = HiddenField(validators=[DataRequired()])
    firstname = StringField(validators=[Optional()])
    lastname = StringField(validators=[Optional()])
    username = StringField(validators=[Optional()])
    email = StringField(validators=[Optional()])
    address = StringField(validators=[Optional()])
    category = SelectField(validators=[Optional()])
    role = SelectField(choices=[("user", "User"), ("admin", "Admin")], validators=[Optional()])
    managed_categories = SelectMultipleField(choices=Category.get_category_options(), validators=[Optional()])
    # Unchecking every box sends no managed_categories at all: this marker tells "cleared" from "not edited"
    managed_categories_submitted = HiddenField()

class AdminDeleteUserForm(FlaskForm):
    user_id = HiddenField(validators=[DataRequired()])

class AdminUpdateEngagementForm(FlaskForm):
    engagement_id = HiddenField(validators=[DataRequired()])
    status = SelectField(
        choices=[
            (EngagementStatus.VALIDATED.value, "Validée"),
            (EngagementStatus.CANCELLED.value, "Refusée"),
        ],
        validators=[DataRequired()],
    )
    # TODO: add reason for cancellation


@admin_bp.route("/admin")
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)

    db = get_db()
    users = db.list_users()
    status_counts = {
        EngagementStatus.PENDING.value: len(db.list_engagements(status=EngagementStatus.PENDING.value)),
        EngagementStatus.VALIDATED.value: len(db.list_engagements(status=EngagementStatus.VALIDATED.value)),
        EngagementStatus.CANCELLED.value: len(db.list_engagements(status=EngagementStatus.CANCELLED.value)),
    }

    return render_template(
        "admin.html",
        user_count=len(users),
        status_counts=status_counts,
    )


@admin_bp.route("/admin/users", methods=["GET", "POST"])
@login_required
def manage_users():
    if current_user.role != "admin":
        abort(403)

    db = get_db()
    users = db.list_users()

    registration_url = current_app.config['external_url'] + "/register?_t=" + db.get_registration_token()

    if request.method == "POST":
        action = request.form.get("_action")
        match action:
            case "create_user":
                form = AdminCreateUserForm()
                form.category.choices = [("", "Aucune")] + Category.get_category_options()

                if form.validate_on_submit():
                    email = (form.email.data or "").strip()
                    password = form.password.data
                    firstname = (form.firstname.data or "").strip()
                    lastname = (form.lastname.data or "").strip()
                    username = (form.username.data or "").strip().lower() or generate_username(db, firstname, lastname)
                    role = (form.role.data or "user").strip()
                    address = (form.address.data or "").strip()
                    category_key = (form.category.data or "").strip()
                    category = Category.from_key(category_key)

                    if not all([firstname, lastname, email, password, role]):
                        flash("Tous les champs sont requis pour créer un utilisateur", "error")
                        return render_template("admin_users.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_email(email):
                        flash("Un utilisateur avec cet email existe déjà", "error")
                        return render_template("admin_users.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_username(username):
                        flash("Un utilisateur avec ce nom d'utilisateur existe déjà", "error")
                        return render_template("admin_users.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)

                    if role.lower() not in ["user", "admin"]:
                        abort(400, description="Rôle invalide sélectionné")

                    managed_categories = [Category.from_key(key) for key in form.managed_categories.data]
                    db.create_user(
                        email=email,
                        username=username,
                        password=password,
                        firstname=firstname,
                        lastname=lastname,
                        category=category,
                        role=role.lower(),
                        managed_categories=managed_categories if role.lower() == "admin" else None,
                        address=address,
                    )
                    flash(f"Le compte de {firstname} {lastname} a été créé")
                    return redirect(url_for("admin.manage_users"))
                flash("Prénom, nom, email et mot de passe sont obligatoires", "error")

            case "update_user":
                form = AdminUpdateUserForm()
                form.category.choices = [("", "Aucune")] + Category.get_category_options()

                if form.validate_on_submit():
                    email = (form.email.data or "").strip() or None
                    firstname = (form.firstname.data or "").strip() or None
                    lastname = (form.lastname.data or "").strip() or None
                    username = (form.username.data or "").strip() or None
                    address = (form.address.data or "").strip() or None
                    role = (form.role.data or "").strip() or None
                    category_key = (form.category.data or "").strip() or None
                    category = Category.from_key(category_key)


                    user_id = int(form.user_id.data)
                    user = db.get_user_by_id(user_id)
                    if not user:
                        abort(404, description="Utilisateur non trouvé")
                    if db.get_user_by_email(email) and db.get_user_by_email(email).id != user_id:
                        flash("Un utilisateur avec cet email existe déjà", "error")
                        return render_template("admin_users.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_username(username) and db.get_user_by_username(username).id != user_id:
                        flash("Un utilisateur avec ce nom d'utilisateur existe déjà", "error")
                        return render_template("admin_users.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if role not in [None, "user", "admin"]:
                        abort(400, description="Rôle invalide sélectionné")
                    if user_id == current_user.user_id and role == "user":
                        flash("Vous ne pouvez pas retirer vos propres droits d'administrateur", "error")
                        return redirect(url_for("admin.manage_users"))

                    managed_categories = None
                    if form.managed_categories_submitted.data and (role or user.role) == "admin":
                        managed_categories = [Category.from_key(key) for key in form.managed_categories.data]

                    db.update_user(
                        user_id=user_id,
                        email=email,
                        username=username,
                        firstname=firstname,
                        lastname=lastname,
                        address=address,
                        category=category,
                        role=role.lower() if role else None,
                        managed_categories=managed_categories
                    )
                    flash(f"Le compte de {firstname or user.firstname} {lastname or user.lastname} a été mis à jour")
                    return redirect(url_for("admin.manage_users"))

            case "delete_user":
                form = AdminDeleteUserForm()
                if form.validate_on_submit():
                    user_id = int(form.user_id.data)
                    user = db.get_user_by_id(user_id)
                    if not user:
                        abort(404, description="Utilisateur non trouvé")
                    if user_id == current_user.user_id:
                        flash("Vous ne pouvez pas supprimer votre propre compte depuis cette page", "error")
                        return redirect(url_for("admin.manage_users"))
                    db.delete_user(user_id)
                    flash(f"Le compte de {user.firstname} {user.lastname} a été supprimé")
                    return redirect(url_for("admin.manage_users"))

            case "regenerate_registration_token":
                form = FlaskForm()
                if form.validate_on_submit():
                    db.regenerate_registration_token()
                    flash("Nouveau lien d'inscription généré, l'ancien lien n'est plus valide")
                    return redirect(url_for("admin.manage_users"))

            case _:
                abort(400, description="Invalid action")

    return render_template(
        "admin_users.html",
        users=users,
        registration_url=registration_url,
        available_category_filters=CATEGORIES,
    )


@admin_bp.route("/admin/engagements", methods=["GET", "POST"])
@login_required
def manage_engagements():
    if current_user.role != "admin":
        abort(403)

    db = get_db()

    if request.method == "POST":
        form = AdminUpdateEngagementForm()
        if form.validate_on_submit():
            engagement_id = int(form.engagement_id.data)
            engagement = db.get_engagement_by_id(engagement_id)
            if not engagement:
                abort(404, description="Engagement non trouvé")
            if engagement.status != EngagementStatus.PENDING.value:
                abort(400, description="Seuls les engagements en statut 'pending' peuvent être mis à jour")

            status_value = form.status.data
            try:
                status = EngagementStatus(status_value)
                if status != EngagementStatus.VALIDATED and status != EngagementStatus.CANCELLED:
                    abort(400, description="Statut invalide sélectionné")
            except ValueError:
                abort(400, description="Statut d'engagement invalide")

            db.update_engagement(engagement_id, status.value)
            rider = f"{engagement.user.firstname} {engagement.user.lastname}"
            race = engagement.race
            decision = "validée" if status == EngagementStatus.VALIDATED else "refusée"
            flash(f"Inscription de {rider} à {race.display_location} {decision}")
            if current_app.config['notify'] and engagement.user.email:
                sent = send_email(
                    to_address=engagement.user.email,
                    subject=f"Votre inscription à {race.display_location} a été {decision}",
                    message=f"Bonjour {engagement.user.firstname},\n\nVotre demande d'inscription à la course de {race.display_location} ({race.department_name}) "
                            f"le {race.long_date().lower()} {race.date.year} a été {decision}.\n\nCordialement,\nASPTT Rennes"
                )
                if not sent:
                    flash(f"L'email de notification n'a pas pu être envoyé à {engagement.user.email}", "error")
            return redirect(url_for("admin.manage_engagements"))

    selected_status = request.args.get("status", default=EngagementStatus.PENDING.value)
    show_all = request.args.get("show_all", default="false").lower() == "true"
    visible_statuses = {
        EngagementStatus.PENDING.value,
        EngagementStatus.VALIDATED.value,
        EngagementStatus.CANCELLED.value,
    }
    if selected_status not in visible_statuses:
        selected_status = EngagementStatus.PENDING.value

    my_managed_categories = db.get_user_by_id(current_user.user_id).managed_categories if current_user.managed_categories else []
    filter_categories = [] if show_all else my_managed_categories

    engagements = sorted(
        db.list_engagements(status=selected_status, categories=filter_categories),
        key=lambda engagement: (
            engagement.race.date,
            engagement.race.location.lower(),
            engagement.user.lastname.lower(),
            engagement.user.firstname.lower(),
        ),
    )
    status_counts = {
        EngagementStatus.PENDING.value: len(db.list_engagements(status=EngagementStatus.PENDING.value, categories=filter_categories)),
        EngagementStatus.VALIDATED.value: len(db.list_engagements(status=EngagementStatus.VALIDATED.value, categories=filter_categories)),
        EngagementStatus.CANCELLED.value: len(db.list_engagements(status=EngagementStatus.CANCELLED.value, categories=filter_categories)),
    }

    return render_template(
        "admin_engagements.html",
        engagements=engagements,
        selected_status=selected_status,
        status_counts=status_counts,
        show_all=show_all,
        has_managed_categories=len(my_managed_categories) > 0,
        update_form=AdminUpdateEngagementForm(),
    )