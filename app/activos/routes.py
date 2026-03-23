from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.models import Activo, Unidad
from . import activos_bp
from app.utils.decorators import require_admin

# LISTAR ACTIVOS DE UNA UNIDAD -----------------------------------
@activos_bp.route("/unidades/<int:unidad_id>/activos")
@login_required
def lista_activos(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    activos = Activo.query.filter_by(unidad_id=unidad_id).order_by(Activo.id.desc()).all()
    return render_template("activos/lista.html", unidad=unidad, activos=activos)


# FORM CREAR (MODAL) ---------------------------------------------
@activos_bp.route("/activos/modal/crear/<int:unidad_id>")
@require_admin
def modal_crear_activo(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    return render_template("activos/modal_form.html", activo=None, unidad=unidad)


# CREAR (POST SUBMIT) --------------------------------------------
@activos_bp.route("/activos/crear/<int:unidad_id>", methods=["POST"])
@require_admin
def crear_activo(unidad_id):
    nombre = request.form.get("nombre")
    tipo = request.form.get("tipo")
    descripcion = request.form.get("descripcion")

    activo = Activo(
        unidad_id=unidad_id,
        nombre=nombre,
        tipo=tipo,
        descripcion=descripcion
    )
    db.session.add(activo)
    db.session.commit()

    flash("Activo creado correctamente.", "success")
    return redirect(url_for("activos.lista_activos", unidad_id=unidad_id))


# FORM EDITAR (MODAL) --------------------------------------------
@activos_bp.route("/activos/modal/<int:activo_id>/editar")
@require_admin
def modal_editar_activo(activo_id):
    activo = Activo.query.get_or_404(activo_id)
    unidad = activo.unidad
    return render_template("activos/modal_form.html", activo=activo, unidad=unidad)


# EDITAR (POST SUBMIT) -------------------------------------------
@activos_bp.route("/activos/<int:activo_id>/editar", methods=["POST"])
@require_admin
def editar_activo(activo_id):
    activo = Activo.query.get_or_404(activo_id)

    activo.nombre = request.form.get("nombre")
    activo.tipo = request.form.get("tipo")
    activo.descripcion = request.form.get("descripcion")
    db.session.commit()

    flash("Activo actualizado.", "success")
    return redirect(url_for("activos.lista_activos", unidad_id=activo.unidad_id))


# ELIMINAR --------------------------------------------------------
@activos_bp.route("/activos/<int:activo_id>/eliminar", methods=["POST"])
@require_admin
def eliminar_activo(activo_id):
    activo = Activo.query.get_or_404(activo_id)
    unidad_id = activo.unidad_id

    db.session.delete(activo)
    db.session.commit()

    flash("Activo eliminado.", "info")
    return redirect(url_for("activos.lista_activos", unidad_id=unidad_id))
