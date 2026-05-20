from flask import render_template, redirect, url_for, request, flash, make_response
from flask_login import login_required
from app import db
from app.models import Unidad, Proyecto, Etapa, Solicitud, CuotaMantenimiento, RegistroPago
from . import unidades_bp
from app.utils.decorators import require_admin

from datetime import datetime

from app.services.estado_cuenta_service import (
    parse_fecha,
    generar_estado_cuenta_pdf_data
)

# /////////////////////////////////////////////////////////////

# LISTAR UNIDADES DE UN PROYECTO ----------------------
@unidades_bp.route("/proyectos/<int:proyecto_id>/unidades")
@login_required
def lista_unidades(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)

    # Obtener todas las etapas del proyecto
    etapas = Etapa.query.filter_by(proyecto_id=proyecto_id).order_by(Etapa.id.asc()).all()

    # Diccionario para agrupar unidades por etapa
    unidades_por_etapa = {}

    for etapa in etapas:
        unidades_por_etapa[etapa.id] = Unidad.query.filter_by(
            etapa_id=etapa.id
        ).order_by(Unidad.id.asc()).all()

    return render_template(
        "unidades/lista.html",
        proyecto=proyecto,
        etapas=etapas,
        unidades_por_etapa=unidades_por_etapa
    )


# FORM CREAR (MODAL) --------------------------------
@unidades_bp.route("/modal/crear/<int:proyecto_id>")
@login_required
def modal_crear_unidad(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    etapas = Etapa.query.filter_by(proyecto_id=proyecto_id).all()
    return render_template("unidades/modal_form.html", unidad=None, proyecto=proyecto, etapas=etapas)


# CREAR (POST SUBMIT) -------------------------------
@unidades_bp.route("/unidades/crear/<int:proyecto_id>", methods=["POST"])
@require_admin
def crear_unidad(proyecto_id):
    nombre = (request.form.get("nombre") or "").strip()
    tipo = (request.form.get("tipo") or "").strip()
    etapa_id = request.form.get("etapa_id")

    if not etapa_id:
        flash("Debe seleccionar una etapa.", "danger")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    if not nombre:
        flash("Debe indicar el nombre de la unidad.", "danger")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    existente = Unidad.query.filter_by(
        proyecto_id=proyecto_id,
        nombre=nombre
    ).first()

    if existente:
        flash(f"Ya existe una unidad con el nombre '{nombre}' en este proyecto.", "warning")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    unidad = Unidad(
        proyecto_id=proyecto_id,
        etapa_id=etapa_id,
        nombre=nombre,
        tipo=tipo,
    )

    db.session.add(unidad)
    db.session.commit()

    flash("Unidad creada correctamente.", "success")
    return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))



# FORM EDITAR (MODAL) -------------------------------
@unidades_bp.route("/modal/editar/<int:unidad_id>")
@login_required
def modal_editar_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    etapas = Etapa.query.filter_by(proyecto_id=unidad.proyecto_id).all()
    return render_template("unidades/modal_form.html", unidad=unidad, proyecto=unidad.proyecto, etapas=etapas)


# EDITAR (POST SUBMIT) ------------------------------
@unidades_bp.route("/unidades/<int:unidad_id>/editar", methods=["POST"])
@require_admin
def editar_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    nuevo_nombre = (request.form.get("nombre") or "").strip()
    nuevo_tipo = (request.form.get("tipo") or "").strip()
    nueva_etapa_id = request.form.get("etapa_id")

    if not nuevo_nombre:
        flash("Debe indicar el nombre de la unidad.", "danger")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=unidad.proyecto_id))

    duplicada = Unidad.query.filter(
        Unidad.proyecto_id == unidad.proyecto_id,
        Unidad.nombre == nuevo_nombre,
        Unidad.id != unidad.id
    ).first()

    if duplicada:
        flash(f"Ya existe otra unidad con el nombre '{nuevo_nombre}' en este proyecto.", "warning")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=unidad.proyecto_id))

    unidad.nombre = nuevo_nombre
    unidad.tipo = nuevo_tipo

    if nueva_etapa_id:
        unidad.etapa_id = nueva_etapa_id

    db.session.commit()

    flash("Unidad actualizada.", "success")
    return redirect(url_for("unidades.lista_unidades", proyecto_id=unidad.proyecto_id))


# ELIMINAR UNIDAD -----------------------------------
@unidades_bp.route("/unidades/<int:unidad_id>/eliminar", methods=["POST"])
@require_admin
def eliminar_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    proyecto_id = unidad.proyecto_id

    # Validar dependencias
    if unidad.activos:
        flash("No puedes eliminar esta unidad porque tiene activos registrados.", "warning")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    db.session.delete(unidad)
    db.session.commit()

    flash("Unidad eliminada.", "info")
    return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))


@unidades_bp.route("/unidades/<int:unidad_id>")
@login_required
def detalle_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    proyecto = unidad.proyecto
    etapa = unidad.etapa

    # Finanzas
    cuotas = CuotaMantenimiento.query.filter_by(unidad_id=unidad.id)\
                                    .order_by(CuotaMantenimiento.periodo.desc()).all()

    cuotas_pendientes = [c for c in cuotas if c.estado == "Pendiente"]
    total_pendiente = sum(c.monto for c in cuotas if c.estado == "Pendiente")

    # Últimos pagos
    ultimo_pago = None
    for c in cuotas:
        if c.estado == "Pagado" and c.fecha_pago:
            ultimo_pago = c
            break

    activos = unidad.activos

    solicitudes = Solicitud.query.filter_by(unidad_id=unidad.id).order_by(
        Solicitud.fecha_creada.desc()
    ).all()

    solicitudes_abiertas = [s for s in solicitudes if s.estado != "cerrada"]

    cuotas_pendientes = CuotaMantenimiento.query.filter_by(
        unidad_id=unidad.id, estado="Pendiente"
    ).all()

    return render_template(
        "unidades/detalle.html",
        unidad=unidad,
        proyecto=proyecto,
        etapa=etapa,
        activos=activos,
        solicitudes=solicitudes,
        solicitudes_abiertas=solicitudes_abiertas,

        # FINANZAS
        cuotas=cuotas,
        cuotas_pendientes=cuotas_pendientes,
        total_pendiente=total_pendiente,
        ultimo_pago=ultimo_pago
    )

def generar_nombres_unidades(form):
    patron = (form.get("patron") or "").strip()

    nombres = []

    if patron == "lineal":
        prefijo = (form.get("prefijo") or "").strip()
        numero_inicial = int(form.get("numero_inicial") or 1)
        cantidad = int(form.get("cantidad") or 1)
        incremento = int(form.get("incremento") or 1)
        padding = int(form.get("padding") or 0)

        if cantidad < 1:
            raise ValueError("La cantidad debe ser mayor que cero.")

        if incremento < 1:
            raise ValueError("El incremento debe ser mayor que cero.")

        for i in range(cantidad):
            numero = numero_inicial + (i * incremento)
            numero_str = str(numero).zfill(padding) if padding > 0 else str(numero)
            nombres.append(f"{prefijo}{numero_str}")

    elif patron == "por_pisos":
        prefijo = (form.get("prefijo") or "").strip()
        piso_inicial = int(form.get("piso_inicial") or 1)
        cantidad_pisos = int(form.get("cantidad_pisos") or 1)
        unidades_por_piso = int(form.get("unidades_por_piso") or 1)
        numero_inicial_unidad = int(form.get("numero_inicial_unidad") or 1)
        digitos_unidad = int(form.get("digitos_unidad") or 2)

        if cantidad_pisos < 1:
            raise ValueError("La cantidad de pisos debe ser mayor que cero.")

        if unidades_por_piso < 1:
            raise ValueError("Las unidades por piso deben ser mayores que cero.")

        if digitos_unidad < 1:
            raise ValueError("Los dígitos de unidad deben ser mayores que cero.")

        for p in range(cantidad_pisos):
            piso = piso_inicial + p

            for u in range(unidades_por_piso):
                numero_unidad = numero_inicial_unidad + u
                sufijo = str(numero_unidad).zfill(digitos_unidad)
                nombres.append(f"{prefijo}{piso}{sufijo}")

    else:
        raise ValueError("Patrón de nomenclatura inválido.")

    # Evita duplicados dentro del mismo lote
    nombres_unicos = []
    vistos = set()

    for nombre in nombres:
        clave = nombre.strip().upper()
        if clave not in vistos:
            vistos.add(clave)
            nombres_unicos.append(nombre)

    return nombres_unicos

@unidades_bp.route("/unidades/crear-masivo/<int:proyecto_id>", methods=["POST"])
@require_admin
def crear_unidades_masivas(proyecto_id):
    etapa_id = request.form.get("etapa_id")
    tipo = (request.form.get("tipo") or "").strip()

    if not etapa_id:
        flash("Debe seleccionar una etapa.", "danger")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    try:
        nombres = generar_nombres_unidades(request.form)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    if not nombres:
        flash("No se generaron unidades.", "warning")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    # Buscar nombres existentes en el proyecto
    existentes = {
        (u.nombre or "").strip().upper()
        for u in Unidad.query.filter_by(proyecto_id=proyecto_id).all()
    }

    nuevas_unidades = []
    repetidas = []

    for nombre in nombres:
        clave = nombre.strip().upper()

        if clave in existentes:
            repetidas.append(nombre)
            continue

        nuevas_unidades.append(
            Unidad(
                proyecto_id=proyecto_id,
                etapa_id=etapa_id,
                nombre=nombre,
                tipo=tipo
            )
        )
        existentes.add(clave)

    if not nuevas_unidades:
        flash("No se creó ninguna unidad porque todas ya existen.", "warning")
        return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

    db.session.add_all(nuevas_unidades)
    db.session.commit()

    mensaje = f"Se crearon {len(nuevas_unidades)} unidades correctamente."
    if repetidas:
        mensaje += f" Se omitieron {len(repetidas)} porque ya existían."

    flash(mensaje, "success")
    return redirect(url_for("unidades.lista_unidades", proyecto_id=proyecto_id))

# //////////////////////////////////////////////////////////////////////////

@unidades_bp.route("/unidades/<int:unidad_id>/modal-estado-cuenta")
@login_required
def modal_estado_cuenta_unidad(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)
    return render_template("unidades/modal_estado_cuenta.html", unidad=unidad)

@unidades_bp.route("/unidades/<int:unidad_id>/estado-cuenta/pdf", methods=["GET"])
@login_required
def generar_estado_cuenta_pdf(unidad_id):
    unidad = Unidad.query.get_or_404(unidad_id)

    fecha_desde = parse_fecha(request.args.get("desde"))
    fecha_hasta = parse_fecha(request.args.get("hasta"))

    if not fecha_desde or not fecha_hasta:
        flash("Debe seleccionar ambas fechas.", "danger")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    if fecha_desde > fecha_hasta:
        flash("La fecha 'desde' no puede ser mayor que la fecha 'hasta'.", "danger")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    data = generar_estado_cuenta_pdf_data(
        unidad_id=unidad.id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )

    response = make_response(data["pdf"])
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'inline; filename={data["filename"]}'

    return response
    unidad = Unidad.query.get_or_404(unidad_id)
    proyecto = unidad.proyecto
    etapa = unidad.etapa

    fecha_desde = _parse_fecha(request.args.get("desde"))
    fecha_hasta = _parse_fecha(request.args.get("hasta"))

    if not fecha_desde or not fecha_hasta:
        flash("Debe seleccionar ambas fechas.", "danger")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    if fecha_desde > fecha_hasta:
        flash("La fecha 'desde' no puede ser mayor que la fecha 'hasta'.", "danger")
        return redirect(url_for("unidades.detalle_unidad", unidad_id=unidad.id))

    cuotas = (
        CuotaMantenimiento.query
        .filter(
            CuotaMantenimiento.unidad_id == unidad.id,
            CuotaMantenimiento.periodo >= fecha_desde,
            CuotaMantenimiento.periodo <= fecha_hasta
        )
        .order_by(CuotaMantenimiento.periodo.asc())
        .all()
    )

    cliente_nombre = _obtener_cliente_principal(unidad)

    pdf = _build_estado_cuenta_pdf(
        unidad=unidad,
        proyecto=proyecto,
        etapa=etapa,
        cliente_nombre=cliente_nombre,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        cuotas=cuotas
    )

    nombre_archivo = (
        f"estado_cuenta_{unidad.nombre}_"
        f"{fecha_desde.strftime('%Y%m%d')}_{fecha_hasta.strftime('%Y%m%d')}.pdf"
    ).replace(" ", "_")

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename={nombre_archivo}"
    return response