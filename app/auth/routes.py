from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from app import db
from app.models import User

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.activo:
                flash("Tu usuario está inactivo. Contacta al administrador.", "warning")
                return redirect(url_for("auth.login"))

            login_user(user)
            flash("Has iniciado sesión correctamente.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))
        else:
            flash("Correo o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
# @login_required
def register():
    # Por ahora, solo un admin podrá crear usuarios nuevos
    # if not current_user.is_admin():
    #     flash("No tienes permisos para crear usuarios.", "danger")
    #     return redirect(url_for("main.index"))

    if request.method == "POST":
        nombre = request.form.get("nombre")
        email = request.form.get("email")
        password = request.form.get("password")
        rol = request.form.get("rol", "operativo")

        if User.query.filter_by(email=email).first():
            flash("Ya existe un usuario con ese correo.", "warning")
            return redirect(url_for("auth.register"))

        user = User(
            nombre=nombre,
            email=email,
            rol=rol
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Usuario creado correctamente.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))
