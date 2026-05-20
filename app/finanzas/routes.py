# app/finanzas/routes.py
from datetime import datetime, date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import Unidad, UnidadPersona, CuotaMantenimiento
from app import db
from app.models import (
    Proyecto,
    Etapa,
    Unidad,
    CuotaMantenimiento, RegistroPago
)
from app.utils.decorators import require_admin
from . import finanzas_bp
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, case

@finanzas_bp.route("/")
@login_required
@require_admin
def dashboard_financiero():
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)

    if hoy.month == 12:
        inicio_proximo_mes = date(hoy.year + 1, 1, 1)
    else:
        inicio_proximo_mes = date(hoy.year, hoy.month + 1, 1)

    # =========================
    # KPIs principales
    # =========================

    total_facturado_mes = db.session.query(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0)
    ).filter(
        CuotaMantenimiento.periodo >= inicio_mes,
        CuotaMantenimiento.periodo < inicio_proximo_mes
    ).scalar()

    total_cobrado_mes = db.session.query(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0)
    ).filter(
        CuotaMantenimiento.estado == "Pagado",
        CuotaMantenimiento.fecha_pago >= inicio_mes,
        CuotaMantenimiento.fecha_pago < inicio_proximo_mes
    ).scalar()

    pendiente_total = db.session.query(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0)
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).scalar()

    cuotas_pendientes = db.session.query(
        func.count(CuotaMantenimiento.id)
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).scalar()

    unidades_morosas = db.session.query(
        func.count(func.distinct(CuotaMantenimiento.unidad_id))
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).scalar()

    fecha_90_dias = hoy - timedelta(days=90)

    deuda_critica_90 = db.session.query(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0)
    ).filter(
        CuotaMantenimiento.estado == "Pendiente",
        CuotaMantenimiento.periodo <= fecha_90_dias
    ).scalar()

    porcentaje_recaudo = 0
    if total_facturado_mes and total_facturado_mes > 0:
        porcentaje_recaudo = (float(total_cobrado_mes) / float(total_facturado_mes)) * 100

    # =========================
    # Top unidades morosas
    # =========================

    top_morosos = db.session.query(
        Unidad.id.label("unidad_id"),
        Unidad.nombre.label("unidad_nombre"),
        func.count(CuotaMantenimiento.id).label("cuotas_pendientes"),
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0).label("balance"),
        func.min(CuotaMantenimiento.periodo).label("periodo_mas_antiguo")
    ).join(
        CuotaMantenimiento, CuotaMantenimiento.unidad_id == Unidad.id
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).group_by(
        Unidad.id,
        Unidad.nombre
    ).order_by(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0).desc()
    ).limit(10).all()

    # =========================
    # Morosidad por etapa
    # =========================

    morosidad_etapas = db.session.query(
        Etapa.nombre.label("etapa_nombre"),
        Proyecto.nombre.label("proyecto_nombre"),
        func.count(func.distinct(Unidad.id)).label("unidades_morosas"),
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0).label("balance")
    ).join(
        Unidad, Unidad.etapa_id == Etapa.id
    ).join(
        Proyecto, Proyecto.id == Etapa.proyecto_id
    ).join(
        CuotaMantenimiento, CuotaMantenimiento.unidad_id == Unidad.id
    ).filter(
        CuotaMantenimiento.estado == "Pendiente"
    ).group_by(
        Etapa.id,
        Etapa.nombre,
        Proyecto.nombre
    ).order_by(
        func.coalesce(func.sum(CuotaMantenimiento.monto), 0).desc()
    ).all()

    return render_template(
        "finanzas/dashboard.html",
        total_facturado_mes=total_facturado_mes,
        total_cobrado_mes=total_cobrado_mes,
        pendiente_total=pendiente_total,
        cuotas_pendientes=cuotas_pendientes,
        unidades_morosas=unidades_morosas,
        deuda_critica_90=deuda_critica_90,
        porcentaje_recaudo=porcentaje_recaudo,
        top_morosos=top_morosos,
        morosidad_etapas=morosidad_etapas,
    )

def get_resumen_unidad(unidad):
    """Devuelve un pequeño resumen financiero para una unidad."""

    cuotas = unidad.cuotas or []

    pendientes = [c for c in cuotas if c.estado == "Pendiente"]
    pagadas = [c for c in cuotas if c.estado == "Pagado"]

    total_pendientes = len(pendientes)
    monto_pendiente = sum(float(c.monto) for c in pendientes) if pendientes else 0.0

    # Última cuota pagada (por periodo más reciente)
    ultima_pagada = max(pagadas, key=lambda c: c.periodo) if pagadas else None

    # Próxima cuota (pendiente con periodo más cercano)
    proxima = min(pendientes, key=lambda c: c.periodo) if pendientes else None

    # Monto mensual sugerido: desde la etapa (si existe)
    monto_mensual = None
    if unidad.etapa is not None:
        monto_mant = getattr(unidad.etapa, "monto_mantenimiento", None)
        if monto_mant is not None:
            monto_mensual = float(monto_mant)

    return {
        "unidad": unidad,
        "total_pendientes": total_pendientes,
        "monto_pendiente": monto_pendiente,
        "ultima_pagada": ultima_pagada,
        "proxima": proxima,
        "monto_mensual": monto_mensual,
    }

# ============================
# LISTADO GLOBAL DE CUOTAS
# ============================
@finanzas_bp.route("/cuotas")
@login_required
@require_admin
def lista_cuotas():
    proyecto_id = request.args.get("proyecto", type=int)
    etapa_id = request.args.get("etapa", type=int)
    estado = request.args.get("estado", default="todos")
    mes = request.args.get("mes")

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)

    if per_page not in [25, 50, 100, 200]:
        per_page = 25

    query = CuotaMantenimiento.query.join(Unidad)

    if proyecto_id:
        query = query.filter(Unidad.proyecto_id == proyecto_id)

    if etapa_id:
        query = query.filter(Unidad.etapa_id == etapa_id)

    if estado and estado != "todos":
        query = query.filter(CuotaMantenimiento.estado == estado)

    if mes:
        try:
            year, month = map(int, mes.split("-"))
            periodo = date(year, month, 1)
            query = query.filter(CuotaMantenimiento.periodo == periodo)
        except Exception:
            flash("Formato de mes inválido. Use YYYY-MM.", "warning")

    query = query.order_by(
        CuotaMantenimiento.periodo.desc(),
        Unidad.nombre.asc()
    )

    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    cuotas = pagination.items

    proyectos = Proyecto.query.order_by(Proyecto.nombre).all()

    etapas = []
    if proyecto_id:
        etapas = Etapa.query.filter_by(
            proyecto_id=proyecto_id
        ).order_by(Etapa.nombre).all()

    return render_template(
        "finanzas/lista.html",
        cuotas=cuotas,
        pagination=pagination,
        proyectos=proyectos,
        etapas=etapas,
        filtro_proyecto=proyecto_id,
        filtro_etapa=etapa_id,
        filtro_estado=estado,
        filtro_mes=mes,
        page=page,
        per_page=per_page,
    )

@finanzas_bp.route("/cuota/modal/individual")
@login_required
@require_admin
def modal_cuota_individual():
    hoy = datetime.utcnow()

    # ⚠️ Aquí hay una decisión importante:
    # ¿solo unidades ocupadas o todas?
    unidades = (
        Unidad.query
        .join(UnidadPersona, UnidadPersona.unidad_id == Unidad.id)
        .filter(UnidadPersona.es_actual.is_(True))
        .distinct()
        .order_by(Unidad.nombre)
        .all()
    )

    return render_template(
        "finanzas/modal_individual.html",
        unidades=unidades,
        fecha_hoy=hoy
    )

@finanzas_bp.route("/cuota/crear", methods=["POST"])
@login_required
@require_admin
def crear_cuota_individual():

    unidad_id = request.form.get("unidad_id", type=int)
    mes = request.form.get("mes")
    monto = request.form.get("monto")

    if not (unidad_id and mes and monto):
        flash("Todos los campos son obligatorios.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    try:
        year, month = map(int, mes.split("-"))
        periodo = date(year, month, 1)
    except Exception:
        flash("Mes inválido.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    try:
        monto_decimal = Decimal(monto)
        if monto_decimal < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        flash("Monto inválido.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    # Validar existencia de unidad
    unidad = Unidad.query.get_or_404(unidad_id)

    # ⚠️ Validación crítica: evitar duplicados
    existe = CuotaMantenimiento.query.filter_by(
        unidad_id=unidad_id,
        periodo=periodo
    ).first()

    if existe:
        flash("Ya existe una cuota para esa unidad en ese mes.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    cuota = CuotaMantenimiento(
        unidad_id=unidad_id,
        periodo=periodo,
        monto=monto_decimal,
        estado="Pendiente",
        fecha_creacion=datetime.utcnow(),
    )

    db.session.add(cuota)
    db.session.commit()

    flash("Cuota creada correctamente.", "success")
    return redirect(url_for("finanzas.lista_cuotas"))

# ====================================
# MODAL PARA CREAR CUOTAS MASIVAS
# ====================================
@finanzas_bp.route("/cuotas/modal/masivo")
@login_required
@require_admin
def modal_cuota_masiva():
    proyectos = Proyecto.query.order_by(Proyecto.nombre).all()
    hoy = datetime.utcnow()
    return render_template(
        "finanzas/modal_masivo.html",
        proyectos=proyectos,
        fecha_hoy=hoy,
    )


# ====================================
# CREAR CUOTAS MASIVAS POR ETAPA
# ====================================
@finanzas_bp.route("/cuotas/masivo", methods=["POST"])
@login_required
@require_admin
def crear_cuotas_masivas():
    proyecto_id = request.form.get("proyecto_id", type=int)
    etapa_id = request.form.get("etapa_id", type=int)
    mes = request.form.get("mes")  # formato YYYY-MM
    monto = request.form.get("monto")

    if not (proyecto_id and etapa_id and mes and monto):
        flash("Debes completar todos los campos.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    try:
        year, month = map(int, mes.split("-"))
        periodo = date(year, month, 1)
    except Exception:
        flash("Mes inválido. Usa el formato YYYY-MM.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    try:
        monto_decimal = float(monto)
        if monto_decimal < 0:
            raise ValueError
    except Exception:
        flash("Monto inválido.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    # Solo unidades de esa etapa que tengan una relación actual
    unidades = (
        Unidad.query
        .join(UnidadPersona, UnidadPersona.unidad_id == Unidad.id)
        .filter(
            Unidad.etapa_id == etapa_id,
            UnidadPersona.es_actual.is_(True)
        )
        .distinct()
        .all()
    )

    if not unidades:
        flash("La etapa seleccionada no tiene unidades ocupadas registradas.", "warning")
        return redirect(url_for("finanzas.lista_cuotas", proyecto=proyecto_id))

    creadas = 0
    omitidas = 0

    for u in unidades:
        existe = CuotaMantenimiento.query.filter_by(
            unidad_id=u.id,
            periodo=periodo
        ).first()

        if existe:
            omitidas += 1
            continue

        cuota = CuotaMantenimiento(
            unidad_id=u.id,
            periodo=periodo,
            monto=monto_decimal,
            estado="Pendiente",
            fecha_creacion=datetime.utcnow(),
        )
        db.session.add(cuota)
        creadas += 1

    db.session.commit()

    flash(
        f"Cuotas creadas: {creadas}. "
        f"Unidades omitidas (ya tenían cuota): {omitidas}.",
        "success"
    )
    return redirect(url_for("finanzas.lista_cuotas", proyecto=proyecto_id))

# ====================================
# MODAL EDITAR CUOTA INDIVIDUAL
# ====================================
@finanzas_bp.route("/cuotas/modal/<int:cuota_id>/editar")
@login_required
@require_admin
def modal_editar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)
    return render_template("finanzas/modal_form.html", cuota=cuota)


# ====================================
# EDITAR CUOTA INDIVIDUAL (POST)
# ====================================
@finanzas_bp.route("/cuotas/<int:cuota_id>/editar", methods=["POST"])
@login_required
@require_admin
def editar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)

    monto = request.form.get("monto")
    estado = request.form.get("estado")
    fecha_pago_str = request.form.get("fecha_pago")  # opcional

    try:
        cuota.monto = float(monto)
    except Exception:
        flash("Monto inválido.", "warning")
        return redirect(url_for("finanzas.lista_cuotas"))

    cuota.estado = estado

    if fecha_pago_str:
        try:
            cuota.fecha_pago = datetime.strptime(fecha_pago_str, "%Y-%m-%d")
        except Exception:
            flash("Fecha de pago inválida. Usa formato YYYY-MM-DD.", "warning")
    else:
        cuota.fecha_pago = None

    db.session.commit()
    flash("Cuota actualizada correctamente.", "success")
    return redirect(url_for("finanzas.lista_cuotas"))


# ====================================
# ELIMINAR CUOTA (SOLO ADMIN)
# ====================================
@finanzas_bp.route("/cuotas/<int:cuota_id>/eliminar", methods=["POST"])
@login_required
@require_admin
def eliminar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)
    next_url = request.form.get("next") or url_for("finanzas.resumen_unidades")
    db.session.delete(cuota)
    db.session.commit()
    flash("Cuota eliminada correctamente.", "info")
    return redirect(next_url)

# ====================================
# AJAX: OBTENER ETAPAS POR PROYECTO
# ====================================
@finanzas_bp.route("/ajax/etapas/<int:proyecto_id>")
@login_required
@require_admin
def ajax_etapas(proyecto_id):
    etapas = Etapa.query.filter_by(proyecto_id=proyecto_id).order_by(Etapa.nombre).all()
    return jsonify([{"id": e.id, "nombre": e.nombre} for e in etapas])


# ====================================
# MODAL PARA PAGAR CUOTA
# ====================================
@finanzas_bp.route("/cuota/<int:cuota_id>/modal/pagar")
@login_required
@require_admin
def modal_pagar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)
    hoy = datetime.utcnow().strftime("%Y-%m-%d")
    unidad_id = request.args.get("unidad_id", type=int)

    return render_template(
        "finanzas/modal_pagar.html",
        cuota=cuota,
        hoy=hoy,
        unidad_id=unidad_id
    )

@finanzas_bp.route("/cuota/<int:cuota_id>/pagar", methods=["POST"])
@login_required
@require_admin
def pagar_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)

    metodo = request.form.get("metodo_pago")
    referencia = request.form.get("referencia")
    fecha_pago_str = request.form.get("fecha_pago")
    unidad_id = request.form.get("unidad_id", type=int)

    # Convertir fecha manual
    try:
        fecha_pago = datetime.strptime(fecha_pago_str, "%Y-%m-%d")
    except:
        fecha_pago = datetime.utcnow()

    pago = RegistroPago(
        unidad_id=cuota.unidad_id,
        cuota_id=cuota.id,
        monto_pagado=cuota.monto,
        metodo_pago=metodo,
        referencia=referencia,
        fecha_pago=fecha_pago,
    )

    cuota.estado = "Pagado"
    cuota.fecha_pago = fecha_pago

    db.session.add(pago)
    db.session.commit()

    flash("Pago registrado exitosamente.", "success")
    return redirect(request.referrer or url_for("finanzas.resumen_unidades"))

# ====================================
# MODAL: VER DETALLE DE CUOTA
# ====================================
@finanzas_bp.route("/cuota/<int:cuota_id>/modal/ver")
@login_required
@require_admin
def modal_ver_cuota(cuota_id):
    cuota = CuotaMantenimiento.query.get_or_404(cuota_id)
    return render_template(
        "finanzas/modal_ver_cuota.html",
        cuota=cuota
    )

@finanzas_bp.route("/unidades")
@login_required
@require_admin
def resumen_unidades():
    # Filtros
    proyecto_id = request.args.get("proyecto", type=int)
    etapa_id = request.args.get("etapa", type=int)
    filtro_estado = request.args.get("estado", "todos")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # Solo múltiplos de 10, mínimo 10, máximo 200
    if per_page < 10:
        per_page = 10

    if per_page > 200:
        per_page = 200

    if per_page % 10 != 0:
        per_page = 10

    proyectos = Proyecto.query.order_by(Proyecto.nombre).all()

    if proyecto_id:
        etapas = Etapa.query.filter_by(
            proyecto_id=proyecto_id
        ).order_by(Etapa.nombre).all()
    else:
        etapas = Etapa.query.order_by(Etapa.nombre).all()

    unidades_query = Unidad.query

    if proyecto_id:
        unidades_query = unidades_query.filter_by(proyecto_id=proyecto_id)

    if etapa_id:
        unidades_query = unidades_query.filter_by(etapa_id=etapa_id)

    unidades = unidades_query.order_by(Unidad.nombre).all()

    resumenes = [get_resumen_unidad(u) for u in unidades]

    # =========================
    # FILTRO POR ESTADO
    # =========================
    if filtro_estado == "aldia":
        resumenes = [
            r for r in resumenes
            if (r["total_pendientes"] or 0) == 0
        ]

    elif filtro_estado == "pendientes":
        resumenes = [
            r for r in resumenes
            if (r["total_pendientes"] or 0) > 0
            and (r["total_pendientes"] or 0) <= 2
        ]

    elif filtro_estado == "criticos":
        resumenes = [
            r for r in resumenes
            if (r["total_pendientes"] or 0) > 2
        ]

    # =========================
    # KPIs
    # =========================
    balance_total = sum(
        (r["monto_pendiente"] or 0)
        for r in resumenes
    )

    unidades_morosas = sum(
        1 for r in resumenes
        if (r["total_pendientes"] or 0) > 0
    )

    unidades_al_dia = sum(
        1 for r in resumenes
        if (r["total_pendientes"] or 0) == 0
    )

    # =========================
    # ORDENAR POR GRAVEDAD
    # =========================
    resumenes = sorted(
        resumenes,
        key=lambda r: (r["unidad"].nombre or "").lower()
    )

    # =========================
    # PAGINACIÓN
    # =========================
    total_resumenes = len(resumenes)

    total_pages = (
        (total_resumenes + per_page - 1) // per_page
        if total_resumenes > 0 else 1
    )

    if page < 1:
        page = 1

    if page > total_pages:
        page = total_pages

    start = (page - 1) * per_page
    end = start + per_page

    resumenes_paginados = resumenes[start:end]

    return render_template(
        "finanzas/unidades.html",
        resumenes=resumenes_paginados,
        proyectos=proyectos,
        etapas=etapas,
        filtro_proyecto=proyecto_id,
        filtro_etapa=etapa_id,
        filtro_estado=filtro_estado,
        balance_total=balance_total,
        unidades_morosas=unidades_morosas,
        unidades_al_dia=unidades_al_dia,
        total_resumenes=total_resumenes,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )

@finanzas_bp.route("/cuotas/unidad/<int:unidad_id>/historial")
@login_required
@require_admin
def modal_historial_unidad(unidad_id):

    unidad = Unidad.query.get_or_404(unidad_id)

    cuotas = (CuotaMantenimiento.query
              .filter_by(unidad_id=unidad_id)
              .order_by(CuotaMantenimiento.periodo.desc())
              .all())

    return render_template(
        "finanzas/modal_historial_unidad.html",
        unidad=unidad,
        cuotas=cuotas
    )
