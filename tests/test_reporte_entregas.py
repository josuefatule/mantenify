from datetime import date
from decimal import Decimal

from sqlalchemy import event, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import aliased

from app import db
from app.models import (
    CuotaMantenimiento,
    Etapa,
    Persona,
    Proyecto,
    Unidad,
    UnidadPersona,
)
from app.services.finanzas_service import obtener_saldos_pendientes_por_unidad
from app.services.unidades_service import (
    obtener_relacion_principal_actual,
    subconsulta_id_relacion_principal_actual,
)


def iniciar_sesion(client, usuario):
    return client.post(
        "/auth/login",
        data={"email": usuario.email, "password": "clave-prueba"},
    )


def crear_proyecto(nombre="Proyecto Uno"):
    proyecto = Proyecto(nombre=nombre)
    db.session.add(proyecto)
    db.session.flush()
    return proyecto


def crear_etapa(proyecto, nombre="Etapa Uno"):
    etapa = Etapa(
        proyecto_id=proyecto.id,
        nombre=nombre,
        monto_mantenimiento=Decimal("1500.00"),
    )
    db.session.add(etapa)
    db.session.flush()
    return etapa


def crear_unidad(proyecto, nombre, etapa=None):
    unidad = Unidad(
        proyecto_id=proyecto.id,
        etapa_id=etapa.id if etapa else None,
        nombre=nombre,
    )
    db.session.add(unidad)
    db.session.flush()
    return unidad


def crear_persona(nombre):
    persona = Persona(nombre_completo=nombre, activo=True)
    db.session.add(persona)
    db.session.flush()
    return persona


def crear_relacion(
    unidad,
    persona,
    *,
    propietario=False,
    principal=False,
    actual=True,
    fecha_desde=None,
):
    relacion = UnidadPersona(
        unidad_id=unidad.id,
        persona_id=persona.id,
        es_propietario=propietario,
        es_principal=principal,
        es_actual=actual,
        fecha_desde=fecha_desde,
    )
    db.session.add(relacion)
    db.session.flush()
    if fecha_desde is None:
        relacion.fecha_desde = None
        db.session.flush()
    return relacion


def crear_cuota(unidad, monto, estado, mes=1):
    cuota = CuotaMantenimiento(
        unidad_id=unidad.id,
        periodo=date(2026, mes, 1),
        monto=Decimal(monto),
        estado=estado,
    )
    db.session.add(cuota)
    db.session.flush()
    return cuota


def test_usuario_no_autenticado_es_redirigido(client):
    proyecto = crear_proyecto()
    db.session.commit()

    respuesta = client.get(f"/reportes/proyecto/{proyecto.id}/entregas")

    assert respuesta.status_code == 302
    assert "/auth/login" in respuesta.headers["Location"]


def test_usuario_no_admin_no_puede_abrir_reporte(client, usuarios):
    proyecto = crear_proyecto()
    db.session.commit()
    iniciar_sesion(client, usuarios["operativo"])

    respuesta = client.get(f"/reportes/proyecto/{proyecto.id}/entregas")

    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/")


def test_admin_puede_abrir_y_proyecto_inexistente_devuelve_404(client, usuarios):
    proyecto = crear_proyecto()
    crear_unidad(proyecto, "Unidad de prueba")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    respuesta = client.get(f"/reportes/proyecto/{proyecto.id}/entregas")
    inexistente = client.get("/reportes/proyecto/999999/entregas")

    assert respuesta.status_code == 200
    contenido = respuesta.get_data(as_text=True)
    assert "Reporte de Entregas" in contenido
    assert "Volver a Etapas" in contenido
    assert f'href="/{proyecto.id}/etapas"' in contenido
    assert 'class="table-responsive"' in contenido
    assert inexistente.status_code == 404


def test_boton_solo_aparece_a_admin_y_vistas_existentes_responden(client, usuarios):
    proyecto = crear_proyecto()
    db.session.commit()

    iniciar_sesion(client, usuarios["admin"])
    etapas_admin = client.get(f"/{proyecto.id}/etapas")
    financiero = client.get(f"/reportes/proyecto/{proyecto.id}")
    assert etapas_admin.status_code == 200
    assert financiero.status_code == 200
    assert "Reporte de Entregas" in etapas_admin.get_data(as_text=True)

    client.get("/auth/logout")
    iniciar_sesion(client, usuarios["operativo"])
    etapas_operativo = client.get(f"/{proyecto.id}/etapas")
    contenido = etapas_operativo.get_data(as_text=True)
    assert etapas_operativo.status_code == 200
    assert "Reporte Financiero" in contenido
    assert "Reporte de Entregas" not in contenido


def test_incluye_unidades_directas_sin_etapa_y_excluye_otro_proyecto(client, usuarios):
    proyecto = crear_proyecto("Proyecto Incluido")
    otro_proyecto = crear_proyecto("Proyecto Excluido")
    etapa = crear_etapa(proyecto)
    crear_unidad(proyecto, "Unidad con etapa", etapa)
    crear_unidad(proyecto, "Unidad sin etapa")
    crear_unidad(otro_proyecto, "Unidad de otro proyecto")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    assert "Unidad con etapa" in contenido
    assert "Unidad sin etapa" in contenido
    assert "Unidad de otro proyecto" not in contenido


def test_unidad_sin_relacion_muestra_valores_vacios(client, usuarios):
    proyecto = crear_proyecto()
    crear_unidad(proyecto, "Unidad Vacía")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    assert "Sin persona vinculada" in contenido
    assert "—" in contenido


def test_resolver_ignora_historicas_y_aplica_todas_las_prioridades(app):
    proyecto = crear_proyecto()

    unidad_1 = crear_unidad(proyecto, "Prioridad 1")
    comun_1 = crear_relacion(
        unidad_1, crear_persona("Común 1"), fecha_desde=date(2020, 1, 1)
    )
    crear_relacion(
        unidad_1,
        crear_persona("Histórica"),
        propietario=True,
        principal=True,
        actual=False,
        fecha_desde=date(2010, 1, 1),
    )
    propietario_principal = crear_relacion(
        unidad_1,
        crear_persona("Propietaria principal"),
        propietario=True,
        principal=True,
        fecha_desde=date(2025, 1, 1),
    )

    unidad_2 = crear_unidad(proyecto, "Prioridad 2")
    crear_relacion(
        unidad_2,
        crear_persona("Inquilina principal"),
        principal=True,
        fecha_desde=date(2020, 1, 1),
    )
    propietario = crear_relacion(
        unidad_2,
        crear_persona("Propietaria"),
        propietario=True,
        fecha_desde=date(2025, 1, 1),
    )

    unidad_3 = crear_unidad(proyecto, "Prioridad 3")
    crear_relacion(
        unidad_3, crear_persona("Común 3"), fecha_desde=date(2019, 1, 1)
    )
    persona_principal = crear_relacion(
        unidad_3,
        crear_persona("Principal no propietaria"),
        principal=True,
        fecha_desde=date(2025, 1, 1),
    )

    unidad_4 = crear_unidad(proyecto, "Prioridad 4")
    comun_4 = crear_relacion(
        unidad_4, crear_persona("Común 4"), fecha_desde=date(2024, 1, 1)
    )
    db.session.commit()

    assert obtener_relacion_principal_actual(unidad_1).id == propietario_principal.id
    assert obtener_relacion_principal_actual(unidad_1).id != comun_1.id
    assert obtener_relacion_principal_actual(unidad_2).id == propietario.id
    assert obtener_relacion_principal_actual(unidad_3).id == persona_principal.id
    assert obtener_relacion_principal_actual(unidad_4).id == comun_4.id


def test_resolver_desempata_por_fecha_nulos_al_final_y_por_id(app):
    proyecto = crear_proyecto()
    unidad = crear_unidad(proyecto, "Desempates")
    relacion_nula = crear_relacion(
        unidad, crear_persona("Fecha nula"), propietario=True, fecha_desde=None
    )
    relacion_tardia = crear_relacion(
        unidad,
        crear_persona("Fecha tardía"),
        propietario=True,
        fecha_desde=date(2025, 1, 2),
    )
    relacion_temprana_1 = crear_relacion(
        unidad,
        crear_persona("Fecha temprana uno"),
        propietario=True,
        fecha_desde=date(2025, 1, 1),
    )
    relacion_temprana_2 = crear_relacion(
        unidad,
        crear_persona("Fecha temprana dos"),
        propietario=True,
        fecha_desde=date(2025, 1, 1),
    )
    db.session.commit()

    elegida = obtener_relacion_principal_actual(unidad)

    assert relacion_nula.fecha_desde is None
    assert elegida.id == relacion_temprana_1.id
    assert elegida.id < relacion_temprana_2.id
    assert elegida.id not in {relacion_nula.id, relacion_tardia.id}


def test_nombre_y_fecha_provienen_de_la_misma_relacion(client, usuarios):
    proyecto = crear_proyecto()
    unidad = crear_unidad(proyecto, "Unidad Relacionada")
    crear_relacion(
        unidad,
        crear_persona("Persona secundaria"),
        fecha_desde=date(2020, 2, 3),
    )
    crear_relacion(
        unidad,
        crear_persona("Persona seleccionada"),
        propietario=True,
        principal=True,
        fecha_desde=date(2024, 7, 9),
    )
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    assert "Persona seleccionada" in contenido
    assert "09/07/2024" in contenido
    assert "03/02/2020" not in contenido


def test_fecha_nula_muestra_guion(client, usuarios):
    proyecto = crear_proyecto()
    unidad = crear_unidad(proyecto, "Unidad sin fecha")
    relacion = crear_relacion(
        unidad,
        crear_persona("Persona sin fecha"),
        propietario=True,
        principal=True,
        fecha_desde=None,
    )
    db.session.commit()
    assert relacion.fecha_desde is None
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    assert "Persona sin fecha" in contenido
    assert "—" in contenido


def test_saldo_suma_solo_pendientes_y_unidad_sin_cuotas_muestra_cero(client, usuarios):
    proyecto = crear_proyecto()
    con_cuotas = crear_unidad(proyecto, "Con cuotas")
    sin_cuotas = crear_unidad(proyecto, "Sin cuotas")
    crear_cuota(con_cuotas, "1000.10", "Pendiente", 1)
    crear_cuota(con_cuotas, "499.90", "Pendiente", 2)
    crear_cuota(con_cuotas, "300.00", "Pagado", 3)
    crear_cuota(con_cuotas, "800.00", "Anulado", 4)
    db.session.commit()

    saldos = obtener_saldos_pendientes_por_unidad(
        [con_cuotas.id, sin_cuotas.id]
    )
    assert saldos[con_cuotas.id] == Decimal("1500.00")
    assert saldos[sin_cuotas.id] == Decimal("0.00")
    assert obtener_saldos_pendientes_por_unidad([]) == {}
    assert isinstance(saldos[con_cuotas.id], Decimal)

    iniciar_sesion(client, usuarios["admin"])
    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)
    assert "RD$ 1,500.00" in contenido
    assert "RD$ 0.00" in contenido


def test_filtro_unidad_es_parcial_case_insensitive_y_no_mezcla_proyectos(client, usuarios):
    proyecto = crear_proyecto("Proyecto buscado")
    otro = crear_proyecto("Otro proyecto")
    crear_unidad(proyecto, "Apartamento Azul")
    crear_unidad(proyecto, "Casa Verde")
    crear_unidad(otro, "Apartamento Azul Externo")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?unidad=APARTAMENTO"
    ).get_data(as_text=True)

    assert "Apartamento Azul" in contenido
    assert "Casa Verde" not in contenido
    assert "Apartamento Azul Externo" not in contenido


def test_filtro_persona_usa_solo_relacion_seleccionada(client, usuarios):
    proyecto = crear_proyecto()
    unidad = crear_unidad(proyecto, "Unidad Buscable")
    crear_relacion(
        unidad,
        crear_persona("Persona mostrada"),
        propietario=True,
        principal=True,
        fecha_desde=date(2024, 1, 1),
    )
    crear_relacion(unidad, crear_persona("Coincidencia secundaria uno"))
    crear_relacion(unidad, crear_persona("Coincidencia secundaria dos"))
    crear_relacion(
        unidad,
        crear_persona("Coincidencia histórica"),
        actual=False,
        fecha_desde=date(2020, 1, 1),
    )
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    seleccionada = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?persona=MOSTRADA"
    ).get_data(as_text=True)
    secundaria = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?persona=Coincidencia+secundaria"
    ).get_data(as_text=True)
    historica = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?persona=histórica"
    ).get_data(as_text=True)

    assert seleccionada.count("Unidad Buscable") == 1
    assert "Persona mostrada" in seleccionada
    assert "Resultados: 1 unidad" in seleccionada
    assert "Unidad Buscable" not in secundaria
    assert "Unidad Buscable" not in historica


def test_paginacion_es_de_50_y_conserva_filtro_unidad(client, usuarios):
    proyecto = crear_proyecto()
    unidades = [
        Unidad(proyecto_id=proyecto.id, nombre=f"Coincidencia {numero:03d}")
        for numero in range(1, 52)
    ]
    db.session.add_all(unidades)
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    pagina_1 = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?unidad=Coincidencia"
    ).get_data(as_text=True)
    pagina_2 = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas?unidad=Coincidencia&page=2"
    ).get_data(as_text=True)

    assert "Coincidencia 001" in pagina_1
    assert "Coincidencia 051" not in pagina_1
    assert "Coincidencia 051" in pagina_2
    assert "unidad=Coincidencia" in pagina_1
    assert "page=2" in pagina_1


def test_selector_y_filtros_de_etapa_se_restringen_al_proyecto(client, usuarios):
    proyecto = crear_proyecto("Proyecto de etapas")
    otro_proyecto = crear_proyecto("Proyecto externo")
    etapa_1 = crear_etapa(proyecto, "Etapa Primera")
    etapa_2 = crear_etapa(proyecto, "Etapa Segunda")
    etapa_externa = crear_etapa(otro_proyecto, "Etapa Externa")
    crear_unidad(proyecto, "Unidad Primera", etapa_1)
    crear_unidad(proyecto, "Unidad Segunda", etapa_2)
    crear_unidad(proyecto, "Unidad Libre")
    crear_unidad(otro_proyecto, "Unidad Externa", etapa_externa)
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    base = f"/reportes/proyecto/{proyecto.id}/entregas"
    todas = client.get(base).get_data(as_text=True)
    primera = client.get(base, query_string={"etapa_id": etapa_1.id}).get_data(as_text=True)
    sin_etapa = client.get(base, query_string={"etapa_id": "sin_etapa"}).get_data(as_text=True)
    externa = client.get(base, query_string={"etapa_id": etapa_externa.id})
    invalida = client.get(base, query_string={"etapa_id": "no-es-un-id"})

    assert "Etapa Primera" in todas
    assert "Etapa Segunda" in todas
    assert "Etapa Externa" not in todas
    assert 'value="sin_etapa"' in todas
    assert "Unidad Primera" in todas
    assert "Unidad Segunda" in todas
    assert "Unidad Libre" in todas

    assert "Unidad Primera" in primera
    assert "Unidad Segunda" not in primera
    assert "Unidad Libre" not in primera

    assert "Unidad Libre" in sin_etapa
    assert "Unidad Primera" not in sin_etapa

    assert externa.status_code == 200
    assert "La etapa seleccionada no pertenece a este proyecto." in externa.get_data(as_text=True)
    assert "Unidad Externa" not in externa.get_data(as_text=True)
    assert invalida.status_code == 200
    assert "La etapa seleccionada no es válida." in invalida.get_data(as_text=True)


def test_filtros_de_fecha_son_inclusivos_y_excluyen_nulos(client, usuarios):
    proyecto = crear_proyecto()
    casos = [
        ("Antes", date(2025, 12, 31)),
        ("Límite inicial", date(2026, 1, 1)),
        ("Intermedia", date(2026, 3, 15)),
        ("Límite final", date(2026, 6, 30)),
        ("Después", date(2026, 7, 1)),
    ]
    for nombre, fecha in casos:
        unidad = crear_unidad(proyecto, nombre)
        crear_relacion(
            unidad,
            crear_persona(f"Persona {nombre}"),
            propietario=True,
            principal=True,
            fecha_desde=fecha,
        )

    unidad_nula = crear_unidad(proyecto, "Fecha nula")
    crear_relacion(
        unidad_nula,
        crear_persona("Persona fecha nula"),
        propietario=True,
        principal=True,
        fecha_desde=None,
    )
    crear_unidad(proyecto, "Sin relación")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])
    base = f"/reportes/proyecto/{proyecto.id}/entregas"

    desde = client.get(base, query_string={"fecha_desde": "2026-03-15"}).get_data(as_text=True)
    hasta = client.get(base, query_string={"fecha_hasta": "2026-03-15"}).get_data(as_text=True)
    rango = client.get(
        base,
        query_string={"fecha_desde": "2026-01-01", "fecha_hasta": "2026-06-30"},
    ).get_data(as_text=True)

    assert "Intermedia" in desde
    assert "Límite final" in desde
    assert "Antes" not in desde
    assert "Fecha nula" not in desde
    assert "Sin relación" not in desde

    assert "Antes" in hasta
    assert "Intermedia" in hasta
    assert "Después" not in hasta
    assert "Fecha nula" not in hasta

    assert "Límite inicial" in rango
    assert "Intermedia" in rango
    assert "Límite final" in rango
    assert "Antes" not in rango
    assert "Después" not in rango
    assert "Fecha nula" not in rango


def test_fechas_invalidas_y_rango_invertido_muestran_error(client, usuarios):
    proyecto = crear_proyecto()
    crear_unidad(proyecto, "Unidad conservada")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])
    base = f"/reportes/proyecto/{proyecto.id}/entregas"

    fecha_invalida = client.get(
        base,
        query_string={"fecha_desde": "fecha-invalida", "unidad": "conservada"},
    )
    rango_invertido = client.get(
        base,
        query_string={"fecha_desde": "2026-06-30", "fecha_hasta": "2026-01-01"},
    )

    contenido_invalido = fecha_invalida.get_data(as_text=True)
    contenido_invertido = rango_invertido.get_data(as_text=True)
    assert fecha_invalida.status_code == 200
    assert "La fecha inicial no tiene un formato válido." in contenido_invalido
    assert 'value="fecha-invalida"' in contenido_invalido
    assert "Unidad conservada" in contenido_invalido
    assert rango_invertido.status_code == 200
    assert "La fecha inicial no puede ser posterior a la fecha final." in contenido_invertido
    assert 'value="2026-06-30"' in contenido_invertido
    assert 'value="2026-01-01"' in contenido_invertido


def test_persona_y_fecha_filtran_la_misma_relacion_seleccionada(client, usuarios):
    proyecto = crear_proyecto()
    unidad = crear_unidad(proyecto, "Unidad coherente")
    crear_relacion(
        unidad,
        crear_persona("Titular Seleccionada"),
        propietario=True,
        principal=True,
        fecha_desde=date(2024, 5, 10),
    )
    crear_relacion(
        unidad,
        crear_persona("Persona Secundaria"),
        fecha_desde=date(2026, 5, 10),
    )
    unidad_sin_persona = crear_unidad(proyecto, "Unidad sin persona")
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])
    base = f"/reportes/proyecto/{proyecto.id}/entregas"

    por_titular = client.get(base, query_string={"persona": "titular selec"}).get_data(as_text=True)
    por_secundaria = client.get(base, query_string={"persona": "secundaria"}).get_data(as_text=True)
    por_fecha_titular = client.get(
        base,
        query_string={"fecha_desde": "2024-05-10", "fecha_hasta": "2024-05-10"},
    ).get_data(as_text=True)
    por_fecha_secundaria = client.get(
        base,
        query_string={"fecha_desde": "2026-05-10", "fecha_hasta": "2026-05-10"},
    ).get_data(as_text=True)

    assert "Unidad coherente" in por_titular
    assert "10/05/2024" in por_titular
    assert "Unidad coherente" not in por_secundaria
    assert "Unidad sin persona" not in por_titular
    assert "Unidad coherente" in por_fecha_titular
    assert "Titular Seleccionada" in por_fecha_titular
    assert "Unidad coherente" not in por_fecha_secundaria


def test_todos_los_filtros_se_combinan_con_and(client, usuarios):
    proyecto = crear_proyecto()
    etapa_objetivo = crear_etapa(proyecto, "Etapa Objetivo")
    otra_etapa = crear_etapa(proyecto, "Otra Etapa")

    objetivo = crear_unidad(proyecto, "Apartamento A Objetivo", etapa_objetivo)
    crear_relacion(
        objetivo,
        crear_persona("Juan Objetivo"),
        propietario=True,
        principal=True,
        fecha_desde=date(2026, 3, 1),
    )

    etapa_incorrecta = crear_unidad(proyecto, "Apartamento A Otra Etapa", otra_etapa)
    crear_relacion(
        etapa_incorrecta,
        crear_persona("Juan Objetivo"),
        propietario=True,
        principal=True,
        fecha_desde=date(2026, 3, 1),
    )

    persona_incorrecta = crear_unidad(proyecto, "Apartamento A Otra Persona", etapa_objetivo)
    crear_relacion(
        persona_incorrecta,
        crear_persona("Pedro Diferente"),
        propietario=True,
        principal=True,
        fecha_desde=date(2026, 3, 1),
    )

    fecha_incorrecta = crear_unidad(proyecto, "Apartamento A Otra Fecha", etapa_objetivo)
    crear_relacion(
        fecha_incorrecta,
        crear_persona("Juan Objetivo"),
        propietario=True,
        principal=True,
        fecha_desde=date(2025, 1, 1),
    )
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])
    base = f"/reportes/proyecto/{proyecto.id}/entregas"
    filtros = {
        "etapa_id": etapa_objetivo.id,
        "fecha_desde": "2026-01-01",
        "fecha_hasta": "2026-12-31",
        "persona": "juan",
        "unidad": "objetivo",
    }

    combinada = client.get(base, query_string=filtros).get_data(as_text=True)
    contradictoria = client.get(
        base,
        query_string={**filtros, "persona": "persona inexistente"},
    ).get_data(as_text=True)

    assert "Apartamento A Objetivo" in combinada
    assert "Apartamento A Otra Etapa" not in combinada
    assert "Apartamento A Otra Persona" not in combinada
    assert "Apartamento A Otra Fecha" not in combinada
    assert "Resultados: 1 unidad" in combinada
    assert "Resultados: 0 unidades" in contradictoria
    assert "No se encontraron unidades que coincidan con los filtros seleccionados." in contradictoria


def test_relacion_seleccionada_en_sql_coincide_con_resolver_python(app):
    proyecto = crear_proyecto()
    unidades = []

    unidad_prioridad = crear_unidad(proyecto, "Prioridad")
    unidades.append(unidad_prioridad)
    crear_relacion(
        unidad_prioridad,
        crear_persona("Común"),
        fecha_desde=date(2020, 1, 1),
    )
    ganadora = crear_relacion(
        unidad_prioridad,
        crear_persona("Propietaria principal"),
        propietario=True,
        principal=True,
        fecha_desde=date(2026, 1, 1),
    )

    unidad_desempate = crear_unidad(proyecto, "Desempate")
    unidades.append(unidad_desempate)
    desempate_id = crear_relacion(
        unidad_desempate,
        crear_persona("Primera por ID"),
        propietario=True,
        fecha_desde=date(2025, 1, 1),
    )
    crear_relacion(
        unidad_desempate,
        crear_persona("Segunda por ID"),
        propietario=True,
        fecha_desde=date(2025, 1, 1),
    )
    crear_relacion(
        unidad_desempate,
        crear_persona("Nula al final"),
        propietario=True,
        fecha_desde=None,
    )

    unidad_sin_relacion = crear_unidad(proyecto, "Sin relación")
    unidades.append(unidad_sin_relacion)
    db.session.commit()

    subconsulta = subconsulta_id_relacion_principal_actual()
    resultados_sql = dict(
        db.session.query(Unidad.id, subconsulta.label("relacion_id"))
        .filter(Unidad.id.in_([unidad.id for unidad in unidades]))
        .all()
    )

    assert resultados_sql[unidad_prioridad.id] == ganadora.id
    assert resultados_sql[unidad_desempate.id] == desempate_id.id
    assert resultados_sql[unidad_sin_relacion.id] is None
    for unidad in unidades:
        relacion_python = obtener_relacion_principal_actual(unidad)
        id_python = relacion_python.id if relacion_python else None
        assert resultados_sql[unidad.id] == id_python


def test_subconsulta_de_relacion_compila_para_mysql_sin_funcion_de_ventana(app):
    relacion = aliased(UnidadPersona)
    consulta = (
        select(Unidad.id)
        .select_from(Unidad)
        .outerjoin(
            relacion,
            relacion.id == subconsulta_id_relacion_principal_actual(),
        )
    )

    sql = str(consulta.compile(dialect=mysql.dialect())).upper()

    assert "LIMIT" in sql
    assert "ROW_NUMBER" not in sql


def test_paginacion_conserva_los_cinco_filtros_y_total_filtrado(client, usuarios):
    proyecto = crear_proyecto()
    etapa = crear_etapa(proyecto, "Etapa Paginada")
    persona = crear_persona("Persona Paginada")
    unidades = [
        Unidad(
            proyecto_id=proyecto.id,
            etapa_id=etapa.id,
            nombre=f"Coincidencia Paginada {numero:03d}",
        )
        for numero in range(1, 52)
    ]
    db.session.add_all(unidades)
    db.session.flush()
    db.session.add_all(
        [
            UnidadPersona(
                unidad_id=unidad.id,
                persona_id=persona.id,
                es_propietario=True,
                es_principal=True,
                es_actual=True,
                fecha_desde=date(2026, 3, 1),
            )
            for unidad in unidades
        ]
    )
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])
    base = f"/reportes/proyecto/{proyecto.id}/entregas"
    filtros = {
        "etapa_id": str(etapa.id),
        "fecha_desde": "2026-01-01",
        "fecha_hasta": "2026-12-31",
        "persona": "Persona Paginada",
        "unidad": "Coincidencia Paginada",
    }

    pagina_1 = client.get(base, query_string=filtros).get_data(as_text=True)
    pagina_2 = client.get(base, query_string={**filtros, "page": 2}).get_data(as_text=True)

    assert "Resultados: 51 unidades" in pagina_1
    assert "Coincidencia Paginada 051" not in pagina_1
    assert "Coincidencia Paginada 051" in pagina_2
    assert f"etapa_id={etapa.id}" in pagina_1
    assert "fecha_desde=2026-01-01" in pagina_1
    assert "fecha_hasta=2026-12-31" in pagina_1
    assert "persona=Persona+Paginada" in pagina_1
    assert "unidad=Coincidencia+Paginada" in pagina_1
    assert "page=2" in pagina_1
    assert 'name="page"' not in pagina_1


def test_interfaz_reemplaza_q_por_cinco_filtros(client, usuarios):
    proyecto = crear_proyecto()
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    for nombre in ["etapa_id", "fecha_desde", "fecha_hasta", "persona", "unidad"]:
        assert f'name="{nombre}"' in contenido
    assert 'name="q"' not in contenido
    assert "Limpiar filtros" in contenido


def test_proyecto_sin_unidades_muestra_estado_vacio(client, usuarios):
    proyecto = crear_proyecto()
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    contenido = client.get(
        f"/reportes/proyecto/{proyecto.id}/entregas"
    ).get_data(as_text=True)

    assert "Este proyecto no tiene unidades registradas." in contenido


def test_numero_de_consultas_no_crece_por_cada_unidad(client, usuarios):
    proyecto = crear_proyecto()
    persona = crear_persona("Persona Filtro")
    primera_unidad = crear_unidad(proyecto, "Unidad 001")
    crear_relacion(
        primera_unidad,
        persona,
        principal=True,
        fecha_desde=date(2025, 1, 1),
    )
    db.session.commit()
    iniciar_sesion(client, usuarios["admin"])

    def contar_selects():
        consultas = []

        def registrar(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", registrar)
        try:
            respuesta = client.get(
                f"/reportes/proyecto/{proyecto.id}/entregas"
                "?persona=Persona&fecha_desde=2025-01-01"
            )
            assert respuesta.status_code == 200
        finally:
            event.remove(db.engine, "before_cursor_execute", registrar)
        return len(consultas)

    consultas_una_unidad = contar_selects()

    nuevas_unidades = [
        Unidad(proyecto_id=proyecto.id, nombre=f"Unidad {numero:03d}")
        for numero in range(2, 51)
    ]
    db.session.add_all(nuevas_unidades)
    db.session.flush()
    db.session.add_all(
        [
            UnidadPersona(
                unidad_id=unidad.id,
                persona_id=persona.id,
                es_propietario=False,
                es_principal=True,
                es_actual=True,
                fecha_desde=date(2025, 1, 1),
            )
            for unidad in nuevas_unidades
        ]
    )
    db.session.commit()
    consultas_cincuenta_unidades = contar_selects()

    assert consultas_una_unidad <= 8
    assert consultas_cincuenta_unidades <= 8
    assert consultas_cincuenta_unidades <= consultas_una_unidad + 1


def test_no_existe_campo_de_fecha_de_entrega_en_el_modelo(app):
    assert "fecha_entrega" not in Unidad.__table__.columns
