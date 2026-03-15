from flask import Blueprint, flash, current_app, redirect, request, url_for, render_template, abort
from flask_login import login_required, login_user, logout_user, current_user

auth_bp = Blueprint('auth', __name__)

def get_repo():
    return current_app.config["repository"]

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = get_repo().get_user_by_email(email)
        if user and user.verify_password(password):
            login_user(user)
            return redirect(url_for('main.index'))
        
        flash("Email ou mot de passe incorrect")

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté")
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template("register.html")
    
    if request.method == "POST":
        if not has_valid_registration_token(request):
            abort(403)
        
        else:
            name = request.form.get("name")
            email = request.form.get("email")
            password = request.form.get("password")

            if get_repo().get_user_by_email(email) is not None:
                flash("Un compte avec cet email existe déjà")
                return render_template("register.html")

            get_repo().create_user(name, email, password)
            flash("Votre compte a été créé, vous pouvez maintenant vous connecter")
            return redirect(url_for("auth.login"))

def has_valid_registration_token(req) -> bool:
    token = req.form.get("_t", "")
    return token == current_app.config["registration_token"]