from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.models import Solicitud, OrdenTrabajo, CuotaMantenimiento, Unidad
from datetime import datetime

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
@login_required
def index():
    # METRICAS
    solicitudes_abiertas = Solicitud.query.filter(
        Solicitud.estado.in_(["pendiente", "en_proceso"])
    ).count()

    ot_en_proceso = OrdenTrabajo.query.filter_by(estado="en_proceso").count()
    ot_completadas = OrdenTrabajo.query.filter_by(estado="completada").count()
    cuotas_pendientes = CuotaMantenimiento.query.filter_by(estado="Pendiente").count()

    now = datetime.utcnow()
    cuotas_pagadas_mes = CuotaMantenimiento.query.filter(
        CuotaMantenimiento.estado == "Pagado",
        CuotaMantenimiento.fecha_pago >= datetime(now.year, now.month, 1)
    ).count()

    return render_template(
        "index.html",
        solicitudes_abiertas=solicitudes_abiertas,
        ot_en_proceso=ot_en_proceso,
        ot_completadas=ot_completadas,
        cuotas_pendientes=cuotas_pendientes,
        cuotas_pagadas_mes=cuotas_pagadas_mes
    )

@main_bp.route("/ajax/unidades/<int:proyecto_id>")
@login_required
def ajax_unidades_global(proyecto_id):
    unidades = Unidad.query.filter_by(proyecto_id=proyecto_id).all()
    return jsonify([{"id": u.id, "nombre": u.nombre} for u in unidades])