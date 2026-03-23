from datetime import date, datetime
from app.models import CuotaMantenimiento, Unidad
from app import db
from app.utils.fechas import meses_entre

def generar_cuotas_por_propietario(unidad_id, fecha_desde):
    unidad = Unidad.query.get(unidad_id)
    
    if not unidad or not unidad.etapa:
        return 0  # no hay etapa = no hay monto de mantenimiento

    monto = unidad.etapa.monto_mantenimiento

    # Fecha inicial → primer día del mes
    periodo_inicio = date(fecha_desde.year, fecha_desde.month, 1)

    # Fecha final → mes actual
    hoy = datetime.utcnow().date()
    periodo_fin = date(hoy.year, hoy.month, 1)

    meses = meses_entre(periodo_inicio, periodo_fin)

    creadas = 0

    for periodo in meses:
        # verificar si ya existe cuota
        existe = CuotaMantenimiento.query.filter_by(
            unidad_id=unidad.id,
            periodo=periodo
        ).first()

        if existe:
            continue

        cuota = CuotaMantenimiento(
            unidad_id=unidad.id,
            periodo=periodo,
            monto=monto,
            estado="Pendiente",
            fecha_creacion=datetime.utcnow()
        )

        db.session.add(cuota)
        creadas += 1

    db.session.commit()
    return creadas
