from flask import Blueprint, flash, current_app, redirect, request, url_for, render_template, abort
from flask_login import login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Optional

from engagement_course.models import Category
from engagement_course.config import CATEGORY_FILTERS

auth_bp = Blueprint('auth', __name__)


class LoginForm(FlaskForm):
    email_or_username = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


class RegisterForm(FlaskForm):
    registration_token = HiddenField(validators=[DataRequired()])
    firstname = StringField(validators=[DataRequired()])
    lastname = StringField(validators=[DataRequired()])
    username = StringField(validators=[Optional()])
    category = SelectField(validators=[DataRequired()])
    email = StringField(validators=[DataRequired()])
    password = PasswordField(validators=[DataRequired()])


def _category_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for level, numbers in CATEGORY_FILTERS.items():
        for number in numbers:
            key = f"{level}_{number}"
            options.append((key, f"{level} {number}"))
    return options


def get_repo():
    return current_app.config["repository"]

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()

    if form.validate_on_submit():
        email_or_username = form.email_or_username.data.strip()
        password = form.password.data

        user = get_repo().get_user_by_email(email_or_username) or get_repo().get_user_by_username(email_or_username)
        if user and user.verify_password(password):
            login_user(user)
            return redirect(url_for('main.index'))

        flash("Email ou mot de passe incorrect")

    elif request.method == 'POST':
        flash("Veuillez remplir tous les champs obligatoires")

    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté")
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    category_options = [("", "Select a category")] + _category_options()
    form = RegisterForm()
    form.category.choices = category_options

    if request.method == "GET":
        form.registration_token.data = request.args.get("_t", "")

    if form.validate_on_submit():
        if not has_valid_registration_token(form.registration_token.data):
            abort(403)

        email = (form.email.data or "").strip()
        username = (form.username.data or "").strip()
        password = form.password.data
        firstname = (form.firstname.data or "").strip()
        lastname = (form.lastname.data or "").strip()
        category_key = form.category.data
        category = Category.from_key(category_key)

        if category is None:
            flash("Veuillez remplir tous les champs obligatoires")
            return render_template("register.html", form=form)

        if get_repo().get_user_by_email(email) is not None:
            flash("Un compte avec cet email existe déjà")
            return render_template("register.html", form=form)

        if username and get_repo().get_user_by_username(username) is not None:
            flash("Un compte avec ce nom d'utilisateur existe déjà")
            return render_template("register.html", form=form)

        get_repo().create_user(
            email=email,
            username=username,
            password=password,
            firstname=firstname,
            lastname=lastname,
            category=category,
            role="user",
        )
        flash("Votre compte a été créé, vous pouvez maintenant vous connecter")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        flash("Veuillez remplir tous les champs obligatoires")

    return render_template("register.html", form=form)


def has_valid_registration_token(token: str) -> bool:
    return token == current_app.config["registration_token"]