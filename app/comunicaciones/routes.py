from datetime import date, datetime

from flask import render_template, request, redirect, url_for, flash, jsonify
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

    if not persona_id:
        flash("Debe seleccionar un destinatario.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    if not asunto:
        flash("Debe indicar el asunto del correo.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    if not cuerpo:
        flash("Debe escribir el mensaje del correo.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    relacion = UnidadPersona.query.filter_by(
        unidad_id=unidad.id,
        persona_id=persona_id,
        es_actual=True
    ).first()

    if not relacion:
        flash("La persona seleccionada no está relacionada actualmente con esta unidad.", "danger")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    persona = relacion.persona

    if not persona.email:
        flash("La persona seleccionada no tiene correo registrado.", "warning")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    adjuntos = []

    if adjuntar_estado:
        fecha_desde = parse_fecha(request.form.get("fecha_desde"))
        fecha_hasta = parse_fecha(request.form.get("fecha_hasta"))

        if not fecha_desde or not fecha_hasta:
            flash("Debe seleccionar el rango de fechas para adjuntar el estado de cuenta.", "warning")
            return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

        if fecha_desde > fecha_hasta:
            flash("La fecha desde no puede ser mayor que la fecha hasta.", "warning")
            return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

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
                fecha_desde=fecha_desde if adjuntar_estado else None,
                fecha_hasta=fecha_hasta if adjuntar_estado else None,
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
            comunicacion = Comunicacion(
                tipo="individual",
                unidad_id=unidad.id,
                persona_id=persona.id if persona else None,
                enviado_por_id=current_user.id,
                email_destino=persona.email if persona and persona.email else "",
                asunto=asunto,
                cuerpo=cuerpo,
                incluye_estado_cuenta=adjuntar_estado,
                fecha_desde=fecha_desde if adjuntar_estado else None,
                fecha_hasta=fecha_hasta if adjuntar_estado else None,
                estado="error",
                error=str(e),
                enviado_en=datetime.utcnow()
            )

            db.session.add(comunicacion)
            db.session.commit()

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