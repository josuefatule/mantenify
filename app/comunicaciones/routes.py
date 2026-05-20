from datetime import date, datetime

from flask import render_template, request, url_for, flash, jsonify
from flask_login import login_required, current_user

from app import db
from . import comunicaciones_bp
from app.models import Unidad, UnidadPersona, Comunicacion
from app.utils.decorators import require_admin
from app.comunicaciones.services import enviar_correo
from app.services.estado_cuenta_service import (
    parse_fecha,
    generar_estado_cuenta_pdf_data
)


def json_error(message, status_code=400):
    return jsonify({
        "success": False,
        "message": message
    }), status_code


@comunicaciones_bp.route("/comunicaciones")
@login_required
@require_admin
def index():
    return render_template("comunicaciones/index.html")


@comunicaciones_bp.route("/comunicaciones/unidad/<int:unidad_id>/modal")
@login_required
@require_admin
def modal_enviar_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    relaciones = (
        UnidadPersona.query
        .filter_by(unidad_id=unidad.id, es_actual=True)
        .join(UnidadPersona.persona)
        .all()
    )

    hoy = date.today()
    desde_default = date(hoy.year, 1, 1)

    return render_template(
        "comunicaciones/modal_enviar_unidad.html",
        unidad=unidad,
        relaciones=relaciones,
        hoy=hoy,
        desde_default=desde_default
    )


@comunicaciones_bp.route("/comunicaciones/unidad/<int:unidad_id>/enviar", methods=["POST"])
@login_required
@require_admin
def enviar_comunicacion_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    persona_id = request.form.get("persona_id", type=int)
    asunto = (request.form.get("asunto") or "").strip()
    cuerpo = (request.form.get("cuerpo") or "").strip()
    adjuntar_estado = request.form.get("adjuntar_estado") == "on"

    fecha_desde = None
    fecha_hasta = None
    persona = None
    adjuntos = []

    if not persona_id:
        return json_error("Debe seleccionar un destinatario.")

    if not asunto:
        return json_error("Debe indicar el asunto del correo.")

    if not cuerpo:
        return json_error("Debe escribir el mensaje del correo.")

    relacion = UnidadPersona.query.filter_by(
        unidad_id=unidad.id,
        persona_id=persona_id,
        es_actual=True
    ).first()

    if not relacion:
        return json_error(
            "La persona seleccionada no está relacionada actualmente con esta unidad.",
            404
        )

    persona = relacion.persona

    if not persona:
        return json_error("No se encontró la persona seleccionada.", 404)

    if not persona.email:
        return json_error("La persona seleccionada no tiene correo registrado.")

    if adjuntar_estado:
        fecha_desde = parse_fecha(request.form.get("fecha_desde"))
        fecha_hasta = parse_fecha(request.form.get("fecha_hasta"))

        if not fecha_desde or not fecha_hasta:
            return json_error(
                "Debe seleccionar el rango de fechas para adjuntar el estado de cuenta."
            )

        if fecha_desde > fecha_hasta:
            return json_error("La fecha desde no puede ser mayor que la fecha hasta.")

        try:
            estado_data = generar_estado_cuenta_pdf_data(
                unidad_id=unidad.id,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                persona_id=persona.id
            )

            adjuntos.append({
                "filename": estado_data["filename"],
                "content_type": "application/pdf",
                "data": estado_data["pdf"]
            })

        except Exception as e:
            return json_error(
                f"Error generando el estado de cuenta: {str(e)}",
                500
            )

    try:
        enviar_correo(
            asunto=asunto,
            destinatarios=[persona.email],
            cuerpo=cuerpo,
            adjuntos=adjuntos
        )

        comunicacion = Comunicacion(
            tipo="individual",
            unidad_id=unidad.id,
            persona_id=persona.id,
            enviado_por_id=current_user.id,
            email_destino=persona.email,
            asunto=asunto,
            cuerpo=cuerpo,
            incluye_estado_cuenta=adjuntar_estado,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            estado="enviada",
            error=None,
            enviado_en=datetime.utcnow()
        )

        db.session.add(comunicacion)
        db.session.commit()

        flash(f"Correo enviado correctamente a {persona.nombre_completo}.", "success")

        return jsonify({
            "success": True,
            "message": "Correo enviado correctamente.",
            "redirect_url": url_for("unidades.detalle_unidad", unidad_id=unidad.id)
        })

    except Exception as e:
        db.session.rollback()

        try:
            comunicacion = Comunicacion(
                tipo="individual",
                unidad_id=unidad.id,
                persona_id=persona.id if persona else None,
                enviado_por_id=current_user.id,
                email_destino=persona.email if persona and persona.email else "",
                asunto=asunto,
                cuerpo=cuerpo,
                incluye_estado_cuenta=adjuntar_estado,
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                estado="error",
                error=str(e),
                enviado_en=datetime.utcnow()
            )

            db.session.add(comunicacion)
            db.session.commit()

        except Exception:
            db.session.rollback()

        return jsonify({
            "success": False,
            "message": f"Error enviando correo: {str(e)}"
        }), 500


@comunicaciones_bp.route("/comunicaciones/unidad/<int:unidad_id>/historial")
@login_required
@require_admin
def historial_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    comunicaciones = (
        Comunicacion.query
        .filter_by(unidad_id=unidad.id)
        .order_by(Comunicacion.creado_en.desc())
        .all()
    )

    return render_template(
        "comunicaciones/historial_unidad.html",
        unidad=unidad,
        comunicaciones=comunicaciones
    )