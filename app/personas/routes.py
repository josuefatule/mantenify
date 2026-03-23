from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from app import db
from . import personas_bp
from app.utils.decorators import require_admin, require_operativo_o_admin
from datetime import date, datetime
from app.models import Unidad, UnidadPersona, Persona, Proyecto
from app.finanzas.hooks import generar_cuotas_por_propietario


# ============================
# LISTADO DE PERSONAS
# ============================
@personas_bp.route("/personas")
@login_required
def lista_personas():
    personas = Persona.query.order_by(Persona.nombre_completo.asc()).all()
    return render_template("personas/lista.html", personas=personas)


# ============================
# MODAL CREAR
# ============================
@personas_bp.route("/personas/modal/crear")
@require_admin
def modal_crear_persona():
    return render_template("personas/modal_form.html", persona=None)


# ============================
# CREAR (POST)
# ============================
@personas_bp.route("/personas/crear", methods=["POST"])
@require_admin
def crear_persona():
    nombre_completo = request.form.get("nombre_completo")
    email = request.form.get("email")
    telefono = request.form.get("telefono")
    identificacion = request.form.get("identificacion")
    direccion = request.form.get("direccion")

    # Validación correo único
    if email and Persona.query.filter_by(email=email).first():
        flash("El correo ya está registrado.", "warning")
        return redirect(url_for("personas.lista_personas"))

    persona = Persona(
        nombre_completo=nombre_completo,
        email=email,
        telefono=telefono,
        identificacion=identificacion,
        direccion=direccion,
        activo=True
    )

    db.session.add(persona)
    db.session.commit()

    flash("Persona creada correctamente.", "success")
    return redirect(url_for("personas.lista_personas"))


# ============================
# MODAL EDITAR
# ============================
@personas_bp.route("/personas/modal/<int:persona_id>/editar")
@require_admin
def modal_editar_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)
    return render_template("personas/modal_form.html", persona=persona)


# ============================
# EDITAR (POST)
# ============================
@personas_bp.route("/personas/<int:persona_id>/editar", methods=["POST"])
@require_admin
def editar_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)

    persona.nombre_completo = request.form.get("nombre_completo")
    persona.email = request.form.get("email")
    persona.telefono = request.form.get("telefono")
    persona.identificacion = request.form.get("identificacion")
    persona.direccion = request.form.get("direccion")

    db.session.commit()

    flash("Persona actualizada.", "success")
    return redirect(url_for("personas.lista_personas"))


# ============================
# DESACTIVAR
# ============================
@personas_bp.route("/personas/<int:persona_id>/toggle", methods=["POST"])
@require_admin
def toggle_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)
    persona.activo = not persona.activo
    db.session.commit()

    flash("Estado actualizado.", "info")
    return redirect(url_for("personas.lista_personas"))

@personas_bp.route("/personas/<int:persona_id>/eliminar", methods=["POST"])
@require_admin
def eliminar_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)

    # Verificar si tiene relaciones con unidades (UnidadPersona)
    if persona.unidades and len(persona.unidades) > 0:
        flash("No puedes eliminar esta persona porque está asociada a una o más unidades.", "warning")
        return redirect(url_for("personas.lista_personas"))

    db.session.delete(persona)
    db.session.commit()

    flash("Persona eliminada correctamente.", "info")
    return redirect(url_for("personas.lista_personas"))

# ================================
# DETALLE DE PERSONA
# ================================
@personas_bp.route("/persona/<int:persona_id>")
@login_required
def detalle_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)

    # Relaciones actuales (propietario o inquilino)
    relaciones_actuales = (
        UnidadPersona.query
        .filter_by(persona_id=persona.id, es_actual=True)
        .all()
    )

    # Historial de relaciones
    relaciones_pasadas = (
        UnidadPersona.query
        .filter_by(persona_id=persona.id, es_actual=False)
        .order_by(UnidadPersona.fecha_hasta.desc())
        .all()
    )

    return render_template(
        "personas/detalle.html",
        persona=persona,
        relaciones_actuales=relaciones_actuales,
        relaciones_pasadas=relaciones_pasadas
    )


# ================================
# MODAL PARA ASOCIAR DESDE PERSONA
# ================================
@personas_bp.route("/persona/<int:persona_id>/modal/asociar")
@require_admin
def modal_asociar_desde_persona(persona_id):
    persona = Persona.query.get_or_404(persona_id)
    proyectos = Proyecto.query.all()
    fecha_hoy = datetime.utcnow()

    return render_template(
        "personas/modal_asociar_desde_persona.html",
        persona=persona,
        proyectos=proyectos,
        fecha_hoy=fecha_hoy
    )


# ===================================
# ROUTE PARA CREAR RELACIÓN DESDE PERSONA
# ===================================
@personas_bp.route("/persona/<int:persona_id>/asociar", methods=["POST"])
@require_admin
def asociar_desde_persona(persona_id):

    from app.finanzas.hooks import generar_cuotas_por_propietario

    persona = Persona.query.get_or_404(persona_id)

    unidad_id = request.form.get("unidad_id")

    # 🔥 propietario / inquilino
    tipo = request.form.get("tipo")
    es_propietario = (tipo == "propietario")

    # 🔥 principal
    es_principal = ("principal" in request.form)

    # 🔥 Fecha desde
    fecha_desde_str = request.form.get("fecha_desde")
    try:
        fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
    except:
        fecha_desde = datetime.utcnow().date()

    # 🔥 Desactivar relaciones previas activas con esta misma unidad
    relaciones_previas = UnidadPersona.query.filter_by(
        persona_id=persona_id,
        unidad_id=unidad_id,
        es_actual=True
    ).all()

    for r in relaciones_previas:
        r.es_actual = False
        r.fecha_hasta = fecha_desde

    # 🔥 Crear nueva relación
    nueva = UnidadPersona(
        persona_id=persona.id,
        unidad_id=unidad_id,
        es_propietario=es_propietario,
        es_principal=es_principal,
        fecha_desde=fecha_desde,
        es_actual=True
    )

    db.session.add(nueva)
    db.session.commit()

    # 🔥 Ejecutar hook si es propietario
    if es_propietario:
        creadas = generar_cuotas_por_propietario(unidad_id, fecha_desde)
        flash(f"Relación creada. Cuotas generadas: {creadas}.", "success")
    else:
        flash("Relación creada correctamente.", "success")

    return redirect(url_for("personas.detalle_persona", persona_id=persona.id))


@personas_bp.route("/personas/modal/asociar/<int:unidad_id>")
@login_required
@require_operativo_o_admin
def modal_asociar_persona(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    personas = Persona.query.filter_by(activo=True).order_by(Persona.nombre_completo).all()
    print("DEBUG personas encontradas:", personas)
    return render_template("personas/modal_asociar.html",
                           unidad=unidad,
                           personas=personas, fecha_hoy = datetime.utcnow().date())


# ---------------------------------------------------------
# POST - Asociar persona
# ---------------------------------------------------------

@personas_bp.route("/unidades/<int:unidad_id>/asociar", methods=["POST"])
@require_admin
def asociar_persona(unidad_id):

    from app.finanzas.hooks import generar_cuotas_por_propietario

    persona_id = request.form.get("persona_id")

    # 🔥 Tipo de relación (propietario / inquilino)
    tipo = request.form.get("tipo")
    es_propietario = (tipo == "propietario")

    # 🔥 Checkbox de principal
    es_principal = ("principal" in request.form)

    # 🔥 Fecha desde
    fecha_desde_str = request.form.get("fecha_desde")
    try:
        fecha_desde = datetime.strptime(fecha_desde_str, "%Y-%m-%d").date()
    except:
        fecha_desde = datetime.utcnow().date()

    # 🔥 Desactivar relaciones previas activas entre esta persona y esta unidad
    relaciones_previas = UnidadPersona.query.filter_by(
        unidad_id=unidad_id,
        persona_id=persona_id,
        es_actual=True
    ).all()

    for r in relaciones_previas:
        r.es_actual = False
        r.fecha_hasta = fecha_desde

    # 🔥 Crear nueva relación
    nueva_rel = UnidadPersona(
        unidad_id=unidad_id,
        persona_id=persona_id,
        es_propietario=es_propietario,
        es_principal=es_principal,
        fecha_desde=fecha_desde,
        es_actual=True
    )

    db.session.add(nueva_rel)
    db.session.commit()

    # 🔥 Ejecutar HOOK solo si es propietario
    if es_propietario:
        creadas = generar_cuotas_por_propietario(unidad_id, fecha_desde)
        flash(f"Persona asociada. Cuotas generadas: {creadas}.", "success")
    else:
        flash("Persona asociada correctamente.", "success")

    return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad_id))




# ---------------------------------------------------------
# DESACTIVAR RELACIÓN
# ---------------------------------------------------------
@personas_bp.route("/personas/relacion/<int:rel_id>/desactivar", methods=["POST"])
@login_required
@require_admin
def desactivar_relacion(rel_id):
    relacion = UnidadPersona.query.get_or_404(rel_id)
    relacion.es_actual = False
    relacion.fecha_hasta = date.today()

    db.session.commit()

    flash("Relación desactivada.", "info")
    return redirect(url_for("unidades.detalle_unidad", unidad_id=relacion.unidad_id))

@personas_bp.route("/relacion/<int:rel_id>/borrar", methods=["POST"])
@require_admin
def borrar_relacion(rel_id):
    rel = UnidadPersona.query.get_or_404(rel_id)

    # Seguridad: No permitir borrar relaciones actuales
    if rel.es_actual:
        flash("No puedes borrar una relación activa. Primero desactívala.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=rel.unidad_id))

    unidad_id = rel.unidad_id

    db.session.delete(rel)
    db.session.commit()

    flash("Relación eliminada del historial.", "success")
    return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad_id))

@personas_bp.route("/relacion/<int:rel_id>/modal/editar")
@require_admin
def modal_editar_relacion(rel_id):
    rel = UnidadPersona.query.get_or_404(rel_id)

    if rel.es_actual:
        flash("No se pueden editar relaciones activas desde aquí.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=rel.unidad_id))

    return render_template("personas/modal_editar_relacion.html", rel=rel)

@personas_bp.route("/relacion/<int:rel_id>/editar", methods=["POST"])
@require_admin
def editar_relacion(rel_id):
    rel = UnidadPersona.query.get_or_404(rel_id)

    if rel.es_actual:
        flash("No puedes editar una relación activa desde esta pantalla.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=rel.unidad_id))

    tipo = request.form.get("tipo")
    rel.es_propietario = (tipo == "propietario")

    rel.es_principal = bool(request.form.get("principal"))

    # Fechas
    fecha_desde = request.form.get("fecha_desde")
    fecha_hasta = request.form.get("fecha_hasta")

    from datetime import datetime

    rel.fecha_desde = datetime.strptime(fecha_desde, "%Y-%m-%d").date()

    if fecha_hasta:
        rel.fecha_hasta = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
    else:
        rel.fecha_hasta = None

    db.session.commit()

    flash("Relación actualizada correctamente.", "success")
    return redirect(url_for("unidades.detalle_unidad", unidad_id=rel.unidad_id))
