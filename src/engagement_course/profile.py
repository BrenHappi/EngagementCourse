from flask import Blueprint, render_template, abort, request, flash, redirect, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SelectMultipleField, SubmitField
from wtforms.validators import Optional, DataRequired
from engagement_course.utils import get_db
from engagement_course.models import Category, RecapSettings, WEEKDAY_LABELS

profile_bp = Blueprint("profile", __name__)

class UpdateProfileForm(FlaskForm):
    firstname = StringField("Prénom", validators=[Optional()])
    lastname = StringField("Nom", validators=[Optional()])
    username = StringField("Nom d'utilisateur", validators=[Optional()])
    category = SelectField(
                            "Catégorie",
                            choices=[("", "Aucune") ] + Category.get_category_options(),
                            validators=[Optional()]
                        )
    managed_categories = SelectMultipleField(
                            "Catégories gérées (pour les admins)",
                            choices=Category.get_category_options(),
                            validators=[Optional()]
            )
    address = StringField("Adresse", validators=[Optional()])
    recap_enabled = BooleanField("Recevoir le récap des inscriptions à valider pour le week-end")
    recap_weekday = SelectField(
                            "Jour",
                            choices=list(enumerate(WEEKDAY_LABELS)),
                            coerce=int,
                            default=RecapSettings.DEFAULT_WEEKDAY,
                            validators=[Optional()]
                        )
    recap_hour = SelectField(
                            "Heure",
                            choices=[(hour, f"{hour}h") for hour in range(6, 24)],
                            coerce=int,
                            default=RecapSettings.DEFAULT_HOUR,
                            validators=[Optional()]
                        )
    current_password = PasswordField("Mot de passe actuel", validators=[Optional()])
    new_password = PasswordField("Nouveau mot de passe", validators=[Optional()])
    confirm_password = PasswordField("Confirmer le nouveau mot de passe", validators=[Optional()])
    submit = SubmitField("Sauvegarder")

class DeleteAccountForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[DataRequired()])
    submit = SubmitField("Supprimer mon compte")


@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()
    user = db.get_user_by_id(current_user.user_id)
    if user is None:
        abort(404, description="User not found")

    profile_form = UpdateProfileForm(obj=user, prefix="profile")
    profile_form.category.data = user.category.to_key() if user.category else ""
    profile_form.managed_categories.data = [
        category.to_key() for category in (user.managed_categories or [])
    ]
    profile_form.address.data = user.address or ""
    recap_settings = db.get_recap_settings(user.user_id)
    profile_form.recap_enabled.data = recap_settings.enabled
    profile_form.recap_weekday.data = recap_settings.weekday
    profile_form.recap_hour.data = recap_settings.hour
    
    if request.method == "POST":
        profile_form = UpdateProfileForm(prefix="profile")
        if profile_form.validate_on_submit():
            firstname = (profile_form.firstname.data).strip() or user.firstname
            lastname = (profile_form.lastname.data).strip() or user.lastname
            username = (profile_form.username.data).strip() or user.username
            category = Category.from_key(profile_form.category.data.strip()) if profile_form.category.data else None
            address = (profile_form.address.data or "").strip()
            managed_categories = [
                category_option
                for category_option in (
                    Category.from_key(category_key)
                    for category_key in profile_form.managed_categories.data
                )
                if category_option is not None
            ]
            
            current_password = profile_form.current_password.data.strip() if profile_form.current_password.data else None
            new_password = profile_form.new_password.data.strip() if profile_form.new_password.data else None
            confirm_password = profile_form.confirm_password.data.strip() if profile_form.confirm_password.data else None
            password_change_requested = any([current_password, new_password, confirm_password])
            
            if password_change_requested and not current_password:
                flash("Le mot de passe actuel est requis pour changer le mot de passe", "error")
            elif password_change_requested and not user.verify_password(current_password):
                flash("Mot de passe actuel incorrect", "error")
            elif password_change_requested and new_password != confirm_password:
                flash("Le nouveau mot de passe et sa confirmation ne correspondent pas", "error")
            else:
                db.update_user(
                    user_id=user.user_id,
                    firstname=firstname,
                    lastname=lastname,
                    username=username,
                    category=category if category else None,
                    managed_categories=managed_categories if user.role == "admin" else None,
                    address=address,
                    password=new_password if password_change_requested and new_password else None
                )
                if user.role == "admin":
                    db.update_recap_settings(
                        user.user_id,
                        enabled=profile_form.recap_enabled.data,
                        weekday=profile_form.recap_weekday.data,
                        hour=profile_form.recap_hour.data,
                    )
                flash("Utilisateur mis à jour avec succès")
                return redirect(url_for("profile.profile"))

    return render_template("profile.html", user=user, profile_form=profile_form)
    

@profile_bp.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    db = get_db()
    user = db.get_user_by_id(current_user.user_id)
    if user is None:
        abort(404, description="User not found")

    delete_form = DeleteAccountForm()
    if delete_form.validate_on_submit():
        current_password = delete_form.current_password.data
        if not user.verify_password(current_password):
            flash("Mot de passe incorrect", "error")
        else:
            db.delete_user(user.user_id)
            flash("Votre compte a été supprimé avec succès")
            return redirect(url_for("auth.login"))

    flash("Une erreur est survenue lors de la suppression du compte", "error")
    return redirect(url_for("profile.profile"))