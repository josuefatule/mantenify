from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

# --------------------------------------
# Solo ADMIN
# --------------------------------------
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != "admin":
            flash("No tienes permisos para acceder a esta sección.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return wrapper


# --------------------------------------
# Solo TÉCNICO
# --------------------------------------
def require_tecnico(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != "tecnico":
            flash("Acceso solo para técnicos.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return wrapper


# --------------------------------------
# Admin u Operativo (no técnico)
# --------------------------------------
def require_operativo_o_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol not in ["admin", "operativo"]:
            flash("Acceso restringido.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)
    return wrapper
