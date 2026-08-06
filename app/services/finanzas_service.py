from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models import CuotaMantenimiento


def obtener_saldos_pendientes_por_unidad(unidad_ids):
    """Devuelve el saldo de cuotas pendientes para cada unidad solicitada."""
    ids = list(dict.fromkeys(unidad_ids))
    saldos = {unidad_id: Decimal("0.00") for unidad_id in ids}

    if not ids:
        return saldos

    resultados = (
        db.session.query(
            CuotaMantenimiento.unidad_id,
            func.sum(CuotaMantenimiento.monto),
        )
        .filter(
            CuotaMantenimiento.unidad_id.in_(ids),
            CuotaMantenimiento.estado == "Pendiente",
        )
        .group_by(CuotaMantenimiento.unidad_id)
        .all()
    )

    for unidad_id, total in resultados:
        saldos[unidad_id] = (
            total if isinstance(total, Decimal) else Decimal(str(total or 0))
        )

    return saldos
