from datetime import datetime, date
from flask import (
    render_template, request, redirect,
    url_for, flash
)
from flask_login import login_required
from app.models import db, Unidad, CuotaMantenimiento, RegistroPago
from . import cuotas_bp
from app.utils.decorators import require_admin

# ===========================
# LISTAR CUOTAS DE UNA UNIDAD
# ===========================
@cuotas_bp.route("/unidad/<int:unidad_id>")
@login_required
def lista_cuotas_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    filtro_estado = request.args.get("estado", "todas")  # todas, Pendiente, Pagado

    query = CuotaMantenimiento.query.filter_by(unidad_id=unidad.id)

    if filtro_estado != "todas":
        query = query.filter_by(estado=filtro_estado)

    cuotas = query.order_by(CuotaMantenimiento.periodo.desc()).all()

    return render_template(
        "cuotas/lista_unidad.html",
        unidad=unidad,
        cuotas=cuotas,
        filtro_estado=filtro_estado
    )


# ===========================
# MODAL CREAR / EDITAR CUOTA
# ===========================
@cuotas_bp.route("/modal/nueva/<int:unidad_id>")
@require_admin
def modal_nueva_cuota(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    # Sugerir mes actual
    hoy = datetime.today()
    periodo_default = hoy.strftime("%Y-%m")  # para <input type="month">

    return render_template(
        "cuotas/modal_form.html",
        unidad=unidad,
        periodo_default=periodo_default
    )


# ===========================
# CREAR CUOTA (POST)
# ===========================
@cuotas_bp.route("/crear/<int:unidad_id>", methods=["POST"])
@require_admin
def crear_cuota(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    periodo_str = request.form.get("periodo")  # formato YYYY-MM
    monto_str = request.form.get("monto")

    if not periodo_str or not monto_str:
        flash("Debe completar periodo y monto.", "danger")
        return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=unidad.id))

    # Convertir periodo a primer día del mes
    try:
        year, month = map(int, periodo_str.split("-"))
        periodo_date = date(year, month, 1)
    except ValueError:
        flash("Periodo inválido.", "danger")
        return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=unidad.id))

    # Evitar duplicados de cuota para mismo mes
    existente = CuotaMantenimiento.query.filter_by(
        unidad_id=unidad.id,
        periodo=periodo_date
    ).first()

    if existente:
        flash("Ya existe una cuota para ese mes en esta unidad.", "warning")
        return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=unidad.id))

    monto = None
    try:
        monto = float(monto_str)
    except ValueError:
        flash("Monto inválido.", "danger")
        return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=unidad.id))

    cuota = CuotaMantenimiento(
        unidad_id=unidad.id,
        periodo=periodo_date,
        monto=monto,
        estado="Pendiente"
    )

    db.session.add(cuota)
    db.session.commit()

    flash("Cuota creada correctamente.", "success")
    return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=unidad.id))


# ===========================
# MARCAR CUOTA COMO PAGADA
# ===========================
@cuotas_bp.route("/pagar/<int:cuota_id>", methods=["POST"])
@require_admin
def pagar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)

    # Solo si está pendiente
    if cuota.estado == "Pagado":
        flash("Esta cuota ya está pagada.", "info")
        return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=cuota.unidad_id))

    # Crear registro de pago
    pago = RegistroPago(
        unidad_id=cuota.unidad_id,
        cuota_id=cuota.id,
        monto_pagado=cuota.monto,
        metodo_pago="manual",      # Lite: más adelante lo mejoramos
        referencia=None
    )

    cuota.estado = "Pagado"
    cuota.fecha_pago = datetime.utcnow()

    db.session.add(pago)
    db.session.commit()

    flash("Cuota marcada como pagada y pago registrado.", "success")
    return redirect(url_for("cuotas.lista_cuotas_unidad", unidad_id=cuota.unidad_id))
