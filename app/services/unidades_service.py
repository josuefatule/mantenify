from datetime import date
from sys import maxsize

from sqlalchemy import and_, case, select

from app.models import Unidad, UnidadPersona


def subconsulta_id_relacion_principal_actual():
    """ID de la relación actual ganadora para la unidad de la consulta externa."""
    prioridad = case(
        (
            and_(
                UnidadPersona.es_propietario.is_(True),
                UnidadPersona.es_principal.is_(True),
            ),
            0,
        ),
        (UnidadPersona.es_propietario.is_(True), 1),
        (UnidadPersona.es_principal.is_(True), 2),
        else_=3,
    )
    fecha_nula = case(
        (UnidadPersona.fecha_desde.is_(None), 1),
        else_=0,
    )

    return (
        select(UnidadPersona.id)
        .where(
            UnidadPersona.unidad_id == Unidad.id,
            UnidadPersona.es_actual.is_(True),
        )
        .order_by(
            prioridad.asc(),
            fecha_nula.asc(),
            UnidadPersona.fecha_desde.asc(),
            UnidadPersona.id.asc(),
        )
        .limit(1)
        .correlate(Unidad)
        .scalar_subquery()
    )


def obtener_relacion_principal_actual(unidad):
    """Selecciona de forma determinista la relación actual a mostrar."""
    relaciones_actuales = [
        relacion
        for relacion in unidad.unidad_personas
        if relacion.es_actual
    ]

    if not relaciones_actuales:
        return None

    def prioridad(relacion):
        if relacion.es_propietario and relacion.es_principal:
            nivel = 0
        elif relacion.es_propietario:
            nivel = 1
        elif relacion.es_principal:
            nivel = 2
        else:
            nivel = 3

        return (
            nivel,
            relacion.fecha_desde is None,
            relacion.fecha_desde or date.max,
            relacion.id if relacion.id is not None else maxsize,
        )

    return min(relaciones_actuales, key=prioridad)
