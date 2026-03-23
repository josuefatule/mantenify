# app/etapas/routes.py
from datetime import date

from flask import render_template, request
from flask_login import login_required

from app.models import Etapa, Unidad, CuotaMantenimiento
from . import etapas_bp


@etapas_bp.route("/etapa/<int:etapa_id>")
@login_required
def detalle_etapa(etapa_id):
    etapa = Etapa.query.get_or_404(etapa_id)

    # ===============================
    # FILTROS DE BÚSQUEDA Y PAGINACIÓN
    # ===============================
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()

    unidades_query = Unidad.query.filter_by(etapa_id=etapa_id)

    if q:
        unidades_query = unidades_query.filter(Unidad.nombre.ilike(f"%{q}%"))

    unidades_paginadas = (
        unidades_query
        .order_by(Unidad.nombre.asc())
        .paginate(page=page, per_page=8, error_out=False)
    )

    unidades = unidades_paginadas.items

    # ===============================
    # FILTROS DE TIEMPO (mes inicio / fin)
    # ===============================
    mes_inicio = request.args.get("inicio")
    mes_fin = request.args.get("fin")

    cuotas_query = (
        CuotaMantenimiento.query
        .join(Unidad)
        .filter(Unidad.etapa_id == etapa_id)
    )

    def str_a_periodo(str_mes):
        y, m = map(int, str_mes.split("-"))
        return date(y, m, 1)

    if mes_inicio:
        inicio_date = str_a_periodo(mes_inicio)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo >= inicio_date)

    if mes_fin:
        fin_date = str_a_periodo(mes_fin)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo <= fin_date)

    cuotas_all = cuotas_query.order_by(CuotaMantenimiento.periodo.desc()).all()

    # ===============================
    # MÉTRICAS PRINCIPALES
    # ===============================
    total_cuotas = sum(float(c.monto) for c in cuotas_all)
    total_pagado = sum(float(c.monto) for c in cuotas_all if c.estado == "Pagado")
    total_pendiente = sum(float(c.monto) for c in cuotas_all if c.estado == "Pendiente")

    hoy = date.today()
    total_moroso = sum(
        float(c.monto)
        for c in cuotas_all
        if c.estado == "Pendiente" and c.periodo < date(hoy.year, hoy.month, 1)
    )

    # ===============================
    # RESUMEN MENSUAL → agrupado por año
    # ===============================
    resumen = {}

    for c in cuotas_all:
        key = c.periodo.strftime("%Y-%m")

        if key not in resumen:
            resumen[key] = {"cuotas": 0.0, "pagado": 0.0, "pendiente": 0.0}

        resumen[key]["cuotas"] += float(c.monto)
        if c.estado == "Pagado":
            resumen[key]["pagado"] += float(c.monto)
        else:
            resumen[key]["pendiente"] += float(c.monto)

    resumen_por_anio = {}
    for ym, info in resumen.items():
        year = ym.split("-")[0]
        resumen_por_anio.setdefault(year, []).append((ym, info))

    for year in resumen_por_anio:
        resumen_por_anio[year].sort(key=lambda t: t[0], reverse=True)

    return render_template(
        "etapas/etapa.html",
        etapa=etapa,
        unidades=unidades,
        pagination=unidades_paginadas,
        q=q,
        total_cuotas=total_cuotas,
        total_pagado=total_pagado,
        total_pendiente=total_pendiente,
        total_moroso=total_moroso,
        resumen_por_anio=resumen_por_anio,
        mes_inicio=mes_inicio,
        mes_fin=mes_fin,
    )