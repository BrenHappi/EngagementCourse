from flask import Blueprint, render_template, current_app, abort, request, flash, redirect, url_for
from flask_login import current_user, login_required
from engagement_course.models import CATEGORIES, Category
from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Optional

admin_bp = Blueprint("admin", __name__)

class AdminCreateUserForm(FlaskForm):
    firstname = StringField(validators=[DataRequired()])
    lastname = StringField(validators=[DataRequired()])
    username = StringField(validators=[Optional()])
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])
    category = SelectField(validators=[Optional()])
    role = SelectField(choices=[("user", "User"), ("admin", "Admin")], validators=[DataRequired()])

class AdminUpdateUserForm(FlaskForm):
    user_id = HiddenField(validators=[DataRequired()])
    firstname = StringField(validators=[Optional()])
    lastname = StringField(validators=[Optional()])
    username = StringField(validators=[Optional()])
    email = StringField(validators=[Optional()])
    category = SelectField(validators=[Optional()])
    role = SelectField(choices=[("user", "User"), ("admin", "Admin")], validators=[Optional()])

class AdminDeleteUserForm(FlaskForm):
    user_id = HiddenField(validators=[DataRequired()])



@admin_bp.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if current_user.role != "admin":
        abort(403)

    db = current_app.config["repository"]
    users = db.list_users()

    registration_url = "http://localhost:3000/register?_t=" + current_app.config['registration_token']

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
                    username = (form.username.data or (firstname[0]+lastname)).strip()
                    role = (form.role.data or "user").strip()
                    category_key = (form.category.data or "").strip()
                    category = Category.from_key(category_key)

                    if not all([firstname, lastname, email, password, role]):
                        flash("Tous les champs sont requis pour créer un utilisateur")
                        return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_email(email):
                        flash("Un utilisateur avec cet email existe déjà")
                        return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_username(username):
                        flash("Un utilisateur avec ce nom d'utilisateur existe déjà")
                        return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)                        

                    if role.lower() not in ["user", "admin"]:
                        abort(400, description="Rôle invalide sélectionné")

                    db.create_user(
                        email=email,
                        username=username,
                        password=password,
                        firstname=firstname,
                        lastname=lastname,
                        category=category,
                        role=role.lower(),
                    )
                    flash("Utilisateur créé avec succès")
                    return redirect(url_for("admin.admin"))

            case "update_user":
                form = AdminUpdateUserForm()
                form.category.choices = [("", "Aucune")] + Category.get_category_options()

                if form.validate_on_submit():
                    email = (form.email.data or "").strip() or None
                    firstname = (form.firstname.data or "").strip() or None
                    lastname = (form.lastname.data or "").strip() or None
                    username = (form.username.data or "").strip() or None
                    role = (form.role.data or "").strip() or None
                    category_key = (form.category.data or "").strip() or None
                    category = Category.from_key(category_key)


                    user_id = int(form.user_id.data)
                    user = db.get_user_by_id(user_id)
                    if not user:
                        abort(404, description="Utilisateur non trouvé")
                    if db.get_user_by_email(email) and db.get_user_by_email(email).id != user_id:
                        flash("Un utilisateur avec cet email existe déjà")
                        return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if db.get_user_by_username(username) and db.get_user_by_username(username).id != user_id:
                        flash("Un utilisateur avec ce nom d'utilisateur existe déjà")
                        return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
                    if role not in ["user", "admin"]:
                        abort(400, description="Rôle invalide sélectionné")

                    db.update_user(
                        user_id=user_id,
                        email=email,
                        username=username,
                        firstname=firstname,
                        lastname=lastname,
                        category=category,
                        role=role.lower() if role else None,
                    )
                    flash(f"Utilisateur {user_id} ({username}) mis à jour avec succès")
                    return redirect(url_for("admin.admin"))

            case "delete_user":
                form = AdminDeleteUserForm()
                if form.validate_on_submit():
                    user_id = int(form.user_id.data)
                    user = db.get_user_by_id(user_id)
                    if not user:
                        abort(404, description="Utilisateur non trouvé")
                    db.delete_user(user_id)
                    flash(f"Utilisateur {user_id} ({user.username}) supprimé avec succès")
                    return redirect(url_for("admin.admin"))

            case _:
                abort(400, description="Invalid action")

    return render_template("admin.html",users=users,registration_url=registration_url,available_category_filters=CATEGORIES)
