from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required
from app import db
from app.models import Proyecto, Etapa, Unidad
from . import proyectos_bp
from app.utils.decorators import require_admin

# LISTA PRINCIPAL
@proyectos_bp.route("/proyectos")
@login_required
def lista_proyectos():
    proyectos = Proyecto.query.order_by(Proyecto.id.desc()).all()
    return render_template("proyectos/lista.html", proyectos=proyectos)


# FORM CREAR (MODAL)
@proyectos_bp.route("/proyectos/modal/crear")
@require_admin
def modal_crear_proyecto():
    return render_template("proyectos/modal_form.html", proyecto=None)


# CREAR (SUBMIT)
@proyectos_bp.route("/proyectos/crear", methods=["POST"])
@require_admin
def crear_proyecto():
    nombre = request.form.get("nombre")
    descripcion = request.form.get("descripcion")

    proyecto = Proyecto(nombre=nombre, descripcion=descripcion)
    db.session.add(proyecto)
    db.session.commit()

    flash("Proyecto creado correctamente.", "success")
    return redirect(url_for("proyectos.lista_proyectos"))


# FORM EDITAR (MODAL)
@proyectos_bp.route("/proyectos/modal/<int:proyecto_id>/editar")
@require_admin
def modal_editar_proyecto(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    return render_template("proyectos/modal_form.html", proyecto=proyecto)


# EDITAR (SUBMIT)
@proyectos_bp.route("/proyectos/<int:proyecto_id>/editar", methods=["POST"])
@require_admin
def editar_proyecto(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)

    proyecto.nombre = request.form.get("nombre")
    proyecto.descripcion = request.form.get("descripcion")
    db.session.commit()

    flash("Proyecto actualizado.", "success")
    return redirect(url_for("proyectos.lista_proyectos"))


# ELIMINAR (SUBMIT DIRECTO)
@proyectos_bp.route("/proyectos/<int:proyecto_id>/eliminar", methods=["POST"])
@require_admin
def eliminar_proyecto(proyecto_id):

    proyecto = Proyecto.query.get_or_404(proyecto_id)

    # Verificar si tiene unidades asociadas
    if proyecto.unidades and len(proyecto.unidades) > 0:
        flash("No puedes eliminar este proyecto porque tiene unidades registradas.", "warning")
        return redirect(url_for("proyectos.lista_proyectos"))

    db.session.delete(proyecto)
    db.session.commit()

    flash("Proyecto eliminado.", "info")
    return redirect(url_for("proyectos.lista_proyectos"))


@proyectos_bp.route("/<int:proyecto_id>/etapas")
@login_required
def etapas_lista(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    etapas = Etapa.query.filter_by(proyecto_id=proyecto_id).all()

    return render_template("etapas/lista.html",
                           proyecto=proyecto,
                           etapas=etapas)

@proyectos_bp.route("/<int:proyecto_id>/etapas/modal/crear")
@login_required
def modal_crear_etapa(proyecto_id):
    proyecto = Proyecto.query.get_or_404(proyecto_id)
    return render_template("etapas/modal_form.html",
                           proyecto=proyecto,
                           etapa=None)

@proyectos_bp.route("/proyecto/<int:proyecto_id>/etapas/crear", methods=["POST"])
@require_admin
def crear_etapa(proyecto_id):

    nombre = request.form.get("nombre")
    descripcion = request.form.get("descripcion")
    monto = request.form.get("monto_mantenimiento") or 0

    etapa = Etapa(
        proyecto_id=proyecto_id,
        nombre=nombre,
        descripcion=descripcion,
        monto_mantenimiento=monto
    )

    db.session.add(etapa)
    db.session.commit()

    flash("Etapa creada correctamente.", "success")
    return redirect(url_for("proyectos.lista_proyectos"))


@proyectos_bp.route("/<int:proyecto_id>/etapas/modal/editar/<int:etapa_id>")
@login_required
def modal_editar_etapa(proyecto_id, etapa_id):
    etapa = Etapa.query.get_or_404(etapa_id)
    proyecto = Proyecto.query.get_or_404(proyecto_id)

    return render_template("etapas/modal_form.html",
                           proyecto=proyecto,
                           etapa=etapa)

@proyectos_bp.route("/proyecto/<int:proyecto_id>/etapa/<int:etapa_id>/editar", methods=["POST"])
@require_admin
def editar_etapa(proyecto_id, etapa_id):

    etapa = Etapa.query.get_or_404(etapa_id)

    etapa.nombre = request.form.get("nombre")
    etapa.descripcion = request.form.get("descripcion")
    etapa.monto_mantenimiento = request.form.get("monto_mantenimiento") or etapa.monto_mantenimiento

    db.session.commit()

    flash("Etapa actualizada correctamente.", "success")
    return redirect(url_for("proyectos.lista_proyectos"))


@proyectos_bp.route("/<int:proyecto_id>/etapas/eliminar/<int:etapa_id>",
                    methods=["POST"])
@login_required
def eliminar_etapa(proyecto_id, etapa_id):
    etapa = Etapa.query.get_or_404(etapa_id)

    if etapa.unidades:
        flash("No puedes eliminar una etapa que tiene unidades asociadas.", "danger")
        return redirect(url_for("proyectos.etapas_lista", proyecto_id=proyecto_id))

    db.session.delete(etapa)
    db.session.commit()

    flash("Etapa eliminada correctamente", "success")
    return redirect(url_for("proyectos.etapas_lista", proyecto_id=proyecto_id))

