from datetime import datetime
from decimal import Decimal
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

from app.models import Unidad, CuotaMantenimiento


def parse_fecha(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def obtener_cliente_principal(unidad):
    """
    Busca primero propietario principal actual.
    Si no existe, toma cualquier propietario actual.
    Si tampoco, toma cualquier persona actual.
    """
    relaciones_actuales = [r for r in unidad.unidad_personas if r.es_actual]

    propietario_principal = next(
        (r for r in relaciones_actuales if r.es_propietario and r.es_principal),
        None
    )

    if propietario_principal:
        return propietario_principal.persona.nombre_completo

    propietario = next(
        (r for r in relaciones_actuales if r.es_propietario),
        None
    )

    if propietario:
        return propietario.persona.nombre_completo

    persona_actual = next(iter(relaciones_actuales), None)

    if persona_actual:
        return persona_actual.persona.nombre_completo

    return "No asignado"


def decimal(valor):
    if valor is None:
        return Decimal("0.00")

    if isinstance(valor, Decimal):
        return valor

    return Decimal(str(valor))


def obtener_cuotas_estado_cuenta(unidad_id, fecha_desde, fecha_hasta):
    return (
        CuotaMantenimiento.query
        .filter(
            CuotaMantenimiento.unidad_id == unidad_id,
            CuotaMantenimiento.periodo >= fecha_desde,
            CuotaMantenimiento.periodo <= fecha_hasta
        )
        .order_by(CuotaMantenimiento.periodo.asc())
        .all()
    )


def build_estado_cuenta_pdf(
    unidad,
    proyecto,
    etapa,
    cliente_nombre,
    fecha_desde,
    fecha_hasta,
    cuotas
):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    elementos = []

    total_facturado = sum((decimal(c.monto) for c in cuotas), Decimal("0.00"))

    total_pagado = sum(
        (
            decimal(c.pago.monto_pagado)
            if c.pago
            else Decimal("0.00")
            for c in cuotas
            if c.estado == "Pagado"
        ),
        Decimal("0.00")
    )

    total_pendiente = sum(
        (decimal(c.monto) for c in cuotas if c.estado != "Pagado"),
        Decimal("0.00")
    )

    cantidad_pagadas = sum(1 for c in cuotas if c.estado == "Pagado")
    cantidad_pendientes = sum(1 for c in cuotas if c.estado != "Pagado")

    # Header con logos
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        img_dir = os.path.join(base_dir, "static", "img")

        company_path = os.path.join(img_dir, "company.png")
        project_path = os.path.join(img_dir, "project.png")

        logo_height = 100

        company_img = Image(
            company_path,
            height=logo_height,
            width=logo_height,
            kind="proportional"
        )

        project_img = Image(
            project_path,
            height=logo_height,
            width=logo_height,
            kind="proportional"
        )

        tabla_header = Table(
            [[company_img, project_img]],
            colWidths=[doc.width / 2, doc.width / 2]
        )

        tabla_header.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        elementos.append(tabla_header)
        elementos.append(Spacer(1, 0.3 * cm))

    except Exception:
        pass

    elementos.append(Paragraph("Estado de Cuenta", styles["Title"]))
    elementos.append(Spacer(1, 0.3 * cm))

    info = [
        ["Proyecto:", proyecto.nombre],
        ["Etapa:", etapa.nombre if etapa else "Sin etapa"],
        ["Unidad:", unidad.nombre],
        ["Cliente:", cliente_nombre],
        ["Rango:", f"{fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}"],
        ["Generado el:", datetime.now().strftime("%d/%m/%Y %I:%M %p")],
    ]

    tabla_info = Table(info, colWidths=[3.2 * cm, 12.8 * cm])
    tabla_info.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabla_info)
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Resumen", styles["Heading2"]))

    resumen_data = [
        ["Total facturado", f"RD$ {total_facturado:,.2f}"],
        ["Total pagado", f"RD$ {total_pagado:,.2f}"],
        ["Total pendiente", f"RD$ {total_pendiente:,.2f}"],
        ["Cuotas pagadas", str(cantidad_pagadas)],
        ["Cuotas pendientes", str(cantidad_pendientes)],
    ]

    tabla_resumen = Table(resumen_data, colWidths=[6.5 * cm, 4.0 * cm])
    tabla_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabla_resumen)
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Detalle de cuotas", styles["Heading2"]))

    detalle_data = [[
        "Periodo", "Monto", "Estado", "Fecha pago", "Método", "Referencia"
    ]]

    for c in cuotas:
        fecha_pago = ""
        metodo_pago = ""
        referencia = ""

        if c.pago:
            fecha_pago = c.pago.fecha_pago.strftime("%d/%m/%Y") if c.pago.fecha_pago else ""
            metodo_pago = c.pago.metodo_pago or ""
            referencia = c.pago.referencia or ""

        elif c.fecha_pago:
            fecha_pago = c.fecha_pago.strftime("%d/%m/%Y")

        detalle_data.append([
            c.periodo.strftime("%Y-%m"),
            f"RD$ {decimal(c.monto):,.2f}",
            c.estado,
            fecha_pago,
            metodo_pago,
            referencia,
        ])

    if len(detalle_data) == 1:
        detalle_data.append(["Sin datos", "", "", "", "", ""])

    tabla_detalle = Table(
        detalle_data,
        colWidths=[2.2 * cm, 2.8 * cm, 2.3 * cm, 2.6 * cm, 2.8 * cm, 3.3 * cm]
    )

    tabla_detalle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))

    for idx, c in enumerate(cuotas, start=1):
        if c.estado == "Pagado":
            tabla_detalle.setStyle(TableStyle([
                ("TEXTCOLOR", (2, idx), (2, idx), colors.green),
                ("FONTNAME", (2, idx), (2, idx), "Helvetica-Bold"),
            ]))
        else:
            tabla_detalle.setStyle(TableStyle([
                ("TEXTCOLOR", (2, idx), (2, idx), colors.red),
                ("FONTNAME", (2, idx), (2, idx), "Helvetica-Bold"),
            ]))

    elementos.append(tabla_detalle)

    doc.build(elementos)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf


def generar_estado_cuenta_pdf_data(unidad_id, fecha_desde, fecha_hasta, persona_id=None):
    """
    Genera el PDF de estado de cuenta en bytes.
    Esta función será reutilizada por:
    - unidades/routes.py para mostrar el PDF.
    - comunicaciones/routes.py para adjuntarlo al correo.
    """

    unidad = Unidad.query.get_or_404(unidad_id)
    proyecto = unidad.proyecto
    etapa = unidad.etapa

    cuotas = obtener_cuotas_estado_cuenta(
        unidad_id=unidad.id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )

    cliente_nombre = obtener_cliente_principal(unidad)

    pdf = build_estado_cuenta_pdf(
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

    return {
        "pdf": pdf,
        "filename": nombre_archivo,
        "unidad": unidad,
        "proyecto": proyecto,
        "etapa": etapa,
        "cuotas": cuotas,
        "cliente_nombre": cliente_nombre,
    }