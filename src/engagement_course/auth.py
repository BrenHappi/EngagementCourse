import hashlib
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import Blueprint, flash, current_app, redirect, request, url_for, render_template, abort
from flask_login import login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import HiddenField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Optional

from engagement_course import config
from engagement_course.mail import send_email
from engagement_course.models import Category, User
from engagement_course.utils import generate_username, get_db, password_problem

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
    confirm_password = PasswordField(validators=[DataRequired()])
    address = StringField(validators=[Optional()])


class ForgotPasswordForm(FlaskForm):
    email = StringField(validators=[DataRequired()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField(validators=[DataRequired()])
    confirm_password = PasswordField(validators=[DataRequired()])


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("calendar.index"))

    db = get_db()
    form = LoginForm()

    if form.validate_on_submit():
        email_or_username = form.email_or_username.data.strip()
        password = form.password.data

        user = db.get_user_by_email(email_or_username) or db.get_user_by_username(email_or_username)
        if user and user.verify_password(password):
            # Stay signed in on this device: members should not have to log in again each time
            login_user(user, remember=True)
            return redirect(_safe_next_url() or url_for('calendar.index'))

        flash("Email ou mot de passe incorrect", "error")

    elif request.method == 'POST':
        flash("Veuillez remplir tous les champs obligatoires", "error")

    return render_template('login.html', form=form)

def _safe_next_url() -> str | None:
    """Page the member wanted before being asked to log in, only if it is on this site."""
    next_url = request.args.get("next") or ""
    if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
        return next_url
    return None


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté")
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    db = get_db()

    category_options = [("", "Choisir…")] + Category.get_category_options()
    form = RegisterForm()
    form.category.choices = category_options

    if request.method == "GET":
        form.registration_token.data = request.args.get("_t", "")
    if not has_valid_registration_token(form.registration_token.data):
        abort(403)

    if form.validate_on_submit():
        email = (form.email.data or "").strip()
        password = form.password.data
        firstname = (form.firstname.data or "").strip()
        lastname = (form.lastname.data or "").strip()
        username = (form.username.data or "").strip() or generate_username(db, firstname, lastname)
        category_key = form.category.data
        category = Category.from_key(category_key)
        address = (form.address.data or "").strip()

        if category is None or not firstname or not lastname:
            flash("Veuillez remplir tous les champs obligatoires", "error")
            return render_template("register.html", form=form)

        if password != form.confirm_password.data:
            flash("Les deux mots de passe ne sont pas identiques", "error")
            return render_template("register.html", form=form)

        if password_problem(password):
            flash(password_problem(password), "error")
            return render_template("register.html", form=form)

        if db.get_user_by_email(email) is not None:
            flash("Un compte avec cet email existe déjà", "error")
            return render_template("register.html", form=form)

        if db.get_user_by_username(username) is not None:
            flash("Un compte avec ce nom d'utilisateur existe déjà", "error")
            return render_template("register.html", form=form)

        db.create_user(
            email=email,
            username=username,
            password=password,
            firstname=firstname,
            lastname=lastname,
            category=category,
            role="user",
            address=address,
        )
        flash("Votre compte a été créé, vous pouvez maintenant vous connecter")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        flash("Veuillez remplir tous les champs obligatoires", "error")

    return render_template("register.html", form=form)


def has_valid_registration_token(token: str) -> bool:
    return bool(token) and secrets.compare_digest(token, get_db().get_registration_token())

def _password_reset_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.secret_key, salt="password-reset")


def _password_fingerprint(user: User) -> str:
    # Changes with the password, so a reset link can only be used once
    password_hash = user.password_hash if isinstance(user.password_hash, bytes) else user.password_hash.encode()
    return hashlib.sha256(password_hash).hexdigest()[:16]


def generate_password_reset_token(user: User) -> str:
    return _password_reset_serializer().dumps({"id": user.user_id, "pw": _password_fingerprint(user)})


def get_user_from_password_reset_token(token: str) -> User | None:
    try:
        data = _password_reset_serializer().loads(token, max_age=config.PASSWORD_RESET_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None
    user = get_db().get_user_by_id(data.get("id"))
    if user is None or not secrets.compare_digest(_password_fingerprint(user), data.get("pw", "")):
        return None
    return user


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if not current_app.config['notify']:
        flash("La réinitialisation par email n'est pas disponible, contactez un administrateur", "error")
        return redirect(url_for('auth.login'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = get_db().get_user_by_email(form.email.data.strip())
        if user is not None:
            reset_url = current_app.config['external_url'] + url_for('auth.reset_password', token=generate_password_reset_token(user))
            send_email(
                to_address=user.email,
                subject="Réinitialisation de votre mot de passe",
                message=f"Bonjour {user.firstname},\n\nPour choisir un nouveau mot de passe, ouvrez ce lien (valable 1 heure) :\n{reset_url}\n\n"
                        f"Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.\n\nCordialement,\nASPTT Rennes"
            )
        # Same answer whether the account exists or not, to avoid leaking registered emails
        flash("Si un compte existe pour cet email, un lien de réinitialisation vient d'être envoyé")
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', form=form)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token: str):
    user = get_user_from_password_reset_token(token)
    if user is None:
        flash("Ce lien de réinitialisation est invalide ou a expiré", "error")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm_password.data:
            flash("Le mot de passe et sa confirmation ne correspondent pas", "error")
        elif password_problem(form.password.data):
            flash(password_problem(form.password.data), "error")
        else:
            get_db().update_user(user_id=user.user_id, password=form.password.data)
            flash("Votre mot de passe a été modifié, vous pouvez maintenant vous connecter")
            return redirect(url_for('auth.login'))
    elif request.method == 'POST':
        flash("Veuillez remplir tous les champs obligatoires", "error")

    return render_template('reset_password.html', form=form, token=token)
