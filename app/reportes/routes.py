from flask import render_template, request
from flask_login import login_required
from app.models import Proyecto, Etapa, Unidad, Persona, UnidadPersona, CuotaMantenimiento
from . import reportes_bp
from datetime import date
from types import SimpleNamespace

# ============================================
# REPORTE POR PROYECTO
# ============================================

def calcular_datos_reporte(proyecto_id, page, mes_inicio, mes_fin, mes_detalle):
    proyecto = Proyecto.query.get_or_404(proyecto_id)

    etapas = proyecto.etapas
    unidades = []
    for e in etapas:
        unidades.extend(e.unidades)

    cuotas_query = CuotaMantenimiento.query.join(Unidad).filter(
        Unidad.id.in_([u.id for u in unidades])
    )

    # FILTROS
    if mes_inicio:
        y, m = map(int, mes_inicio.split("-"))
        inicio_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo >= inicio_date)

    if mes_fin:
        y, m = map(int, mes_fin.split("-"))
        fin_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo <= fin_date)

    if mes_detalle:
        y, m = map(int, mes_detalle.split("-"))
        detalle_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo == detalle_date)

    cuotas_query = cuotas_query.order_by(CuotaMantenimiento.periodo.desc())

    # MÉTRICAS
    cuotas_all = cuotas_query.all()

    total_cuotas = sum(float(c.monto) for c in cuotas_all)
    total_pagado = sum(float(c.monto) for c in cuotas_all if c.estado == "Pagado")
    total_pendiente = sum(float(c.monto) for c in cuotas_all if c.estado == "Pendiente")

    hoy = date.today()
    total_moroso = sum([
        float(c.monto)
        for c in cuotas_all
        if c.estado == "Pendiente" and c.periodo < date(hoy.year, hoy.month, 1)
    ])

    # PAGINACIÓN
    por_pagina = 10
    total = len(cuotas_all)
    start = (page - 1) * por_pagina
    end = start + por_pagina

    cuotas_paginadas = cuotas_all[start:end]
    total_paginas = (total + por_pagina - 1) // por_pagina

    return {
        "proyecto": proyecto,
        "cuotas": cuotas_paginadas,
        "total_paginas": total_paginas,
        "total_cuotas": total_cuotas,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "total_moroso": total_moroso,
        "page": page,
        "mes_inicio": mes_inicio,
        "mes_fin": mes_fin,
        "mes_detalle": mes_detalle,
    }

def calcular_resumen_mensual(proyecto, mes_inicio, mes_fin):
    etapas = proyecto.etapas
    unidades = []
    for e in etapas:
        unidades.extend(e.unidades)

    cuotas = CuotaMantenimiento.query.join(Unidad).filter(
        Unidad.id.in_([u.id for u in unidades])
    ).all()

    def fecha_periodo(str_mes):
        y, m = map(int, str_mes.split("-"))
        return date(y, m, 1)

    inicio_date = fecha_periodo(mes_inicio) if mes_inicio else None
    fin_date = fecha_periodo(mes_fin) if mes_fin else None

    resumen_por_mes = {}

    for c in cuotas:
        if inicio_date and c.periodo < inicio_date:
            continue
        if fin_date and c.periodo > fin_date:
            continue

        key = c.periodo.strftime("%Y-%m")

        if key not in resumen_por_mes:
            resumen_por_mes[key] = {"cuotas": 0, "pagado": 0, "pendiente": 0}

        resumen_por_mes[key]["cuotas"] += float(c.monto)

        if c.estado == "Pagado":
            resumen_por_mes[key]["pagado"] += float(c.monto)
        else:
            resumen_por_mes[key]["pendiente"] += float(c.monto)

    return dict(sorted(resumen_por_mes.items(), reverse=True))

@reportes_bp.route("/proyecto/<int:proyecto_id>")
@login_required
def reporte_proyecto(proyecto_id):

    page = request.args.get("page", 1, type=int)
    mes_inicio = request.args.get("inicio")
    mes_fin = request.args.get("fin")
    mes_detalle = request.args.get("mes_detalle")

    datos = calcular_datos_reporte(proyecto_id, page, mes_inicio, mes_fin, mes_detalle)

    # ============================
    # RESUMEN POR MES (ya lo tenías)
    # ============================
    resumen = calcular_resumen_mensual(datos["proyecto"], mes_inicio, mes_fin)
    # `resumen` es algo tipo: { "2025-01": info, "2025-02": info, ... }

    # ============================
    # AGRUPAR POR AÑO (NUEVO)
    # ============================
    resumen_por_anio = {}

    for mes, info in resumen.items():
        # mes = "2025-01"
        year = mes.split("-")[0]  # "2025"

        if year not in resumen_por_anio:
            resumen_por_anio[year] = []

        # usamos SimpleNamespace para poder hacer row.mes y row.info.cuotas en el template
        resumen_por_anio[year].append(SimpleNamespace(mes=mes, info=info))

    # Ordenar los meses dentro de cada año (de más reciente a más viejo)
    for year, lista in resumen_por_anio.items():
        lista.sort(key=lambda r: r.mes, reverse=True)

    return render_template(
        "reportes/proyecto.html",
        resumen_por_anio=resumen_por_anio,  # ⬅️ nuevo
        **datos
    )

@reportes_bp.route("/proyecto/<int:proyecto_id>/detalle_ajax")
@login_required
def reporte_proyecto_detalle_ajax(proyecto_id):

    page = request.args.get("page", 1, type=int)
    mes_inicio = request.args.get("inicio")
    mes_fin = request.args.get("fin")
    mes_detalle = request.args.get("mes_detalle")

    datos = calcular_datos_reporte(proyecto_id, page, mes_inicio, mes_fin, mes_detalle)

    return render_template(
        "reportes/_detalle_cuotas_parcial.html",
        cuotas=datos["cuotas"],
        page=datos["page"],
        total_paginas=datos["total_paginas"],
        proyecto_id=proyecto_id,
        mes_detalle=mes_detalle,
        mes_inicio=mes_inicio,
        mes_fin=mes_fin
    )

# ============================================
# REPORTE POR ETAPA
# ============================================

def calcular_datos_reporte_etapa(etapa_id, page, mes_inicio, mes_fin, mes_detalle):
    etapa = Etapa.query.get_or_404(etapa_id)
    unidades = etapa.unidades

    cuotas_query = CuotaMantenimiento.query.filter(
        CuotaMantenimiento.unidad_id.in_([u.id for u in unidades])
    )

    # FILTROS
    if mes_inicio:
        y, m = map(int, mes_inicio.split("-"))
        inicio_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo >= inicio_date)

    if mes_fin:
        y, m = map(int, mes_fin.split("-"))
        fin_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo <= fin_date)

    if mes_detalle:
        y, m = map(int, mes_detalle.split("-"))
        filtro_date = date(y, m, 1)
        cuotas_query = cuotas_query.filter(CuotaMantenimiento.periodo == filtro_date)

    cuotas_query = cuotas_query.order_by(CuotaMantenimiento.periodo.desc())
    cuotas_all = cuotas_query.all()

    # MÉTRICAS
    total_cuotas = sum(float(c.monto) for c in cuotas_all)
    total_pagado = sum(float(c.monto) for c in cuotas_all if c.estado == "Pagado")
    total_pendiente = sum(float(c.monto) for c in cuotas_all if c.estado == "Pendiente")

    hoy = date.today()
    total_moroso = sum([
        float(c.monto)
        for c in cuotas_all
        if c.estado == "Pendiente" and c.periodo < date(hoy.year, hoy.month, 1)
    ])

    # PAGINACIÓN
    por_pagina = 6
    total = len(cuotas_all)
    inicio = (page - 1) * por_pagina
    fin = inicio + por_pagina
    cuotas_paginadas = cuotas_all[inicio:fin]

    total_paginas = (total + por_pagina - 1) // por_pagina

    return {
        "etapa": etapa,
        "cuotas": cuotas_paginadas,
        "total_paginas": total_paginas,
        "total_cuotas": total_cuotas,
        "total_pagado": total_pagado,
        "total_pendiente": total_pendiente,
        "total_moroso": total_moroso,
        "page": page,
        "mes_inicio": mes_inicio,
        "mes_fin": mes_fin,
        "mes_detalle": mes_detalle,
    }

def agrupar_resumen_por_anio(resumen):
    """
    Recibe un dict con claves 'YYYY-MM' y valores con totales.
    Devuelve:
    {
        2025: [("2025-03", {...}), ("2025-02", {...})],
        2024: [...],
    }
    """
    resumen_anual = {}

    for mes, datos in resumen.items():
        anio = int(mes.split("-")[0])

        if anio not in resumen_anual:
            resumen_anual[anio] = []

        resumen_anual[anio].append((mes, datos))

    # ordenar por año descendente y por mes descendente dentro del año
    for anio in resumen_anual:
        resumen_anual[anio].sort(key=lambda x: x[0], reverse=True)

    # ordenar el dict final por año descendente
    resumen_anual = dict(sorted(resumen_anual.items(), reverse=True))

    return resumen_anual


@reportes_bp.route("/etapa/<int:etapa_id>")
@login_required
def reporte_etapa(etapa_id):

    page = request.args.get("page", 1, type=int)
    mes_inicio = request.args.get("inicio")
    mes_fin = request.args.get("fin")
    mes_detalle = request.args.get("mes_detalle")

    datos = calcular_datos_reporte_etapa(etapa_id, page, mes_inicio, mes_fin, mes_detalle)

    # Resumen agrupado por año (igual que proyecto)
    resumen = calcular_resumen_mensual(datos["etapa"], mes_inicio, mes_fin)
    resumen_por_anio = agrupar_resumen_por_anio(resumen)

    return render_template(
        "reportes/etapa.html",
        resumen_por_anio=resumen_por_anio,
        **datos
    )

@reportes_bp.route("/etapa/<int:etapa_id>/detalle_ajax")
@login_required
def reporte_etapa_detalle_ajax(etapa_id):

    page = request.args.get("page", 1, type=int)
    mes_inicio = request.args.get("inicio")
    mes_fin = request.args.get("fin")
    mes_detalle = request.args.get("mes_detalle")

    datos = calcular_datos_reporte_etapa(etapa_id, page, mes_inicio, mes_fin, mes_detalle)

    return render_template(
        "reportes/_detalle_cuotas_parcial.html",
        cuotas=datos["cuotas"],
        page=datos["page"],
        total_paginas=datos["total_paginas"],
        etapa_id=etapa_id,
        mes_detalle=mes_detalle,
        mes_inicio=mes_inicio,
        mes_fin=mes_fin
    )


# ============================================
# REPORTE POR UNIDAD
# ============================================
@reportes_bp.route("/unidad/<int:unidad_id>")
@login_required
def reporte_unidad(unidad_id):

    unidad = Unidad.query.get_or_404(unidad_id)

    data = {
        "cuotas": unidad.cuotas,
        "total_pagado": sum([c.monto for c in unidad.cuotas if c.estado == "Pagado"]),
        "total_pendiente": sum([c.monto for c in unidad.cuotas if c.estado == "Pendiente"]),
    }

    return render_template("reportes/unidad.html",
                           unidad=unidad, data=data)


# ============================================
# REPORTE POR PERSONA
# ============================================
@reportes_bp.route("/persona/<int:persona_id>")
@login_required
def reporte_persona(persona_id):

    persona = Persona.query.get_or_404(persona_id)

    relaciones = UnidadPersona.query.filter_by(persona_id=persona.id).all()

    cuotas = CuotaMantenimiento.query.join(Unidad).join(UnidadPersona).filter(
        UnidadPersona.persona_id == persona.id
    ).all()

    data = {
        "relaciones": relaciones,
        "cuotas": cuotas,
        "total_pagado": sum([c.monto for c in cuotas if c.estado == "Pagado"]),
        "total_pendiente": sum([c.monto for c in cuotas if c.estado == "Pendiente"]),
    }

    return render_template("reportes/persona.html",
                           persona=persona, data=data)
