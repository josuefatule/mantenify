# app/main/routes.py
from datetime import datetime
from flask import render_template
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.main import main_bp
from app.models import (
    Solicitud,
    OrdenTrabajo,
    CuotaMantenimiento,
    RegistroPago,
    Unidad,
)


@main_bp.route("/")
@login_required
def index():
    now = datetime.utcnow()
    inicio_mes = datetime(now.year, now.month, 1)

    # =========================
    # OPERACIÓN
    # =========================
    solicitudes_abiertas = Solicitud.query.filter(
        Solicitud.estado.in_(["pendiente", "en_proceso"])
    ).count()

    ot_en_proceso = OrdenTrabajo.query.filter_by(
        estado="en_proceso"
    ).count()

    ot_completadas = OrdenTrabajo.query.filter_by(
        estado="completada"
    ).count()

    # Si tienes campo fecha_fin o fecha_cierre, luego podemos convertir esto a:
    # OT completadas este mes.

    # =========================
    # FINANZAS
    # =========================
    cuotas_pendientes = CuotaMantenimiento.query.filter_by(
        estado="Pendiente"
    ).count()

    cuotas_pagadas_mes = CuotaMantenimiento.query.filter(
        CuotaMantenimiento.estado == "Pagado",
        CuotaMantenimiento.fecha_pago >= inicio_mes
    ).count()

    balance_pendiente_total = db.session.query(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0)
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).scalar()

    unidades_morosas = db.session.query(
        func.count(func.distinct(CuotaMantenimiento.unidad_id))
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).scalar()

    # =========================
    # TOP MOROSOS
    # =========================
    top_morosos = (
        db.session.query(
            Unidad.id.label("unidad_id"),
            Unidad.nombre.label("unidad_nombre"),
            func.count(CuotaMantenimiento.id).label("cuotas_pendientes"),
            func.coalesce(func.sum(CuotaMantenimiento.monto), 0).label("balance"),
            func.min(CuotaMantenimiento.periodo).label("desde"),
        )
        .join(CuotaMantenimiento, CuotaMantenimiento.unidad_id == Unidad.id)
        .filter(CuotaMantenimiento.estado == "Pendiente")
        .group_by(Unidad.id, Unidad.nombre)
        .order_by(func.coalesce(func.sum(CuotaMantenimiento.monto), 0).desc())
        .limit(5)
        .all()
    )

    # =========================
    # RECIENTES
    # =========================
    solicitudes_recientes = (
        Solicitud.query
        .order_by(Solicitud.id.desc())
        .limit(5)
        .all()
    )

    ordenes_recientes = (
        OrdenTrabajo.query
        .order_by(OrdenTrabajo.id.desc())
        .limit(5)
        .all()
    )

    pagos_recientes = (
        RegistroPago.query
        .order_by(RegistroPago.fecha_pago.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "index.html",
        solicitudes_abiertas=solicitudes_abiertas,
        ot_en_proceso=ot_en_proceso,
        ot_completadas=ot_completadas,
        cuotas_pendientes=cuotas_pendientes,
        cuotas_pagadas_mes=cuotas_pagadas_mes,
        balance_pendiente_total=balance_pendiente_total,
        unidades_morosas=unidades_morosas,
        top_morosos=top_morosos,
        solicitudes_recientes=solicitudes_recientes,
        ordenes_recientes=ordenes_recientes,
        pagos_recientes=pagos_recientes,
    )