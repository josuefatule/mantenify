from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Proyecto, Unidad, Activo, Solicitud
from . import solicitudes_bp
from app.utils.decorators import require_operativo_o_admin


# LISTA GENERAL DE SOLICITUDES -------------------------------------
@solicitudes_bp.route("/solicitudes")
@login_required
def lista_solicitudes():
    proyecto_id = request.args.get("proyecto")
    estado = request.args.get("estado") or "todos"

    query = Solicitud.query.order_by(Solicitud.fecha_creada.desc())

    if proyecto_id:
        query = query.filter_by(proyecto_id=proyecto_id)

    if estado != "todos":
        query = query.filter_by(estado=estado)

    solicitudes = query.all()
    proyectos = Proyecto.query.all()

    return render_template(
        "solicitudes/lista.html",
        solicitudes=solicitudes,
        proyectos=proyectos,
        filtro_proyecto=proyecto_id,
        filtro_estado=estado,
    )


# FORM CREAR (MODAL) -----------------------------------------------
@solicitudes_bp.route("/solicitudes/modal/crear")
@require_operativo_o_admin
def modal_crear_solicitud():
    proyectos = Proyecto.query.all()
    return render_template(
        "solicitudes/modal_form.html",
        solicitud=None,
        proyectos=proyectos,
        unidades=[],
        activos=[],
    )


# AJAX PARA CARGAR UNIDADES SEGÚN PROYECTO -------------------------
@solicitudes_bp.route("/solicitudes/ajax/unidades/<int:proyecto_id>")
@require_operativo_o_admin
def ajax_unidades(proyecto_id):
    unidades = Unidad.query.filter_by(proyecto_id=proyecto_id).all()
    return jsonify([{"id": u.id, "nombre": u.nombre} for u in unidades])


# AJAX PARA CARGAR ACTIVOS SEGÚN UNIDAD ----------------------------
@solicitudes_bp.route("/solicitudes/ajax/activos/<int:unidad_id>")
@require_operativo_o_admin
def ajax_activos(unidad_id):
    activos = Activo.query.filter_by(unidad_id=unidad_id).all()
    return jsonify([{"id": a.id, "nombre": a.nombre} for a in activos])


# CREAR (POST SUBMIT) ----------------------------------------------
@solicitudes_bp.route("/solicitudes/crear", methods=["POST"])
@require_operativo_o_admin
def crear_solicitud():
    proyecto_id = request.form.get("proyecto_id")
    unidad_id = request.form.get("unidad_id")
    activo_id = request.form.get("activo_id") or None
    titulo = request.form.get("titulo")
    descripcion = request.form.get("descripcion")
    prioridad = request.form.get("prioridad")

    solicitud = Solicitud(
        proyecto_id=proyecto_id,
        unidad_id=unidad_id,
        activo_id=activo_id,
        titulo=titulo,
        descripcion=descripcion,
        prioridad=prioridad,
        creado_por=current_user.id,
    )

    db.session.add(solicitud)
    db.session.commit()

    flash("Solicitud creada correctamente.", "success")
    return redirect(url_for("solicitudes.lista_solicitudes"))


# FORM EDITAR (MODAL) ----------------------------------------------
@solicitudes_bp.route("/solicitudes/modal/<int:solicitud_id>/editar")
@require_operativo_o_admin
def modal_editar_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    proyectos = Proyecto.query.all()
    unidades = Unidad.query.filter_by(proyecto_id=solicitud.proyecto_id).all()
    activos = Activo.query.filter_by(unidad_id=solicitud.unidad_id).all()

    return render_template(
        "solicitudes/modal_form.html",
        solicitud=solicitud,
        proyectos=proyectos,
        unidades=unidades,
        activos=activos,
    )


# EDITAR (POST) -----------------------------------------------------
@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/editar", methods=["POST"])
@require_operativo_o_admin
def editar_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    solicitud.proyecto_id = request.form.get("proyecto_id")
    solicitud.unidad_id = request.form.get("unidad_id")
    solicitud.activo_id = request.form.get("activo_id") or None
    solicitud.titulo = request.form.get("titulo")
    solicitud.descripcion = request.form.get("descripcion")
    solicitud.prioridad = request.form.get("prioridad")

    db.session.commit()

    flash("Solicitud actualizada.", "success")
    return redirect(url_for("solicitudes.lista_solicitudes"))


# CAMBIAR ESTADO (cerrar, reabrir) ----------------------------------
@solicitudes_bp.route("/solicitudes/<int:solicitud_id>/estado", methods=["POST"])
@require_operativo_o_admin
def cambiar_estado_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    nuevo_estado = request.form.get("estado")

    solicitud.estado = nuevo_estado
    db.session.commit()

    flash("Estado actualizado.", "success")
    return redirect(url_for("solicitudes.lista_solicitudes"))


# DETALLE -----------------------------------------------------------
@solicitudes_bp.route("/solicitudes/<int:solicitud_id>")
@login_required
def detalle_solicitud(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)
    return render_template("solicitudes/detalle.html", solicitud=solicitud)
