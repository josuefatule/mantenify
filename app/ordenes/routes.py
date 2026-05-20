from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from app.models import db, Solicitud, OrdenTrabajo, User
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image
import os
import io
from . import ordenes_bp
from .. import db
from flask import send_file
from app.models import Adjunto, OrdenTrabajo
from app.utils.decorators import require_operativo_o_admin, require_admin, require_tecnico
from . import ordenes_bp

@ordenes_bp.route("/")
@login_required
@require_operativo_o_admin
def lista_ordenes():
    ordenes = OrdenTrabajo.query.order_by(OrdenTrabajo.id.desc()).all()
    return render_template("ordenes/lista.html", ordenes=ordenes)

# ===========================
# CREAR OT DESDE UNA SOLICITUD
# ===========================
@ordenes_bp.route("/crear/<int:solicitud_id>")
@require_admin
def crear_ot(solicitud_id):
    solicitud = Solicitud.query.get_or_404(solicitud_id)

    # Validación: si ya existe una OT → redirige
    if solicitud.orden:
        flash("La solicitud ya tiene una Orden de Trabajo.", "warning")
        return redirect(url_for("ordenes.detalle_ot", ot_id=solicitud.orden.id))

    # Crear OT
    ot = OrdenTrabajo(
        solicitud_id=solicitud.id,
        tecnico_id=None,  # se puede asignar después
    )

    db.session.add(ot)
    db.session.commit()

    flash("Orden de Trabajo creada exitosamente.", "success")
    return redirect(url_for("ordenes.detalle_ot", ot_id=ot.id))


# ===========================
# VER DETALLE DE OT
# ===========================
@ordenes_bp.route("/<int:ot_id>")
@login_required
def detalle_ot(ot_id):
    ot = OrdenTrabajo.query.get_or_404(ot_id)
    tecnicos = User.query.filter_by(rol="tecnico", activo=True).all()

    return render_template("ordenes/detalle.html", ot=ot, tecnicos=tecnicos)


# ===========================
# ASIGNAR TÉCNICO
# ===========================
@ordenes_bp.route("/asignar/<int:ot_id>", methods=["POST"])
@require_operativo_o_admin
def asignar_tecnico(ot_id):
    ot = OrdenTrabajo.query.get_or_404(ot_id)
    tecnico_id = request.form.get("tecnico_id")

    ot.tecnico_id = tecnico_id
    db.session.commit()

    flash("Técnico asignado correctamente.", "success")
    return redirect(url_for("ordenes.detalle_ot", ot_id=ot.id))


# ===========================
# CAMBIAR ESTADO
# ===========================
@ordenes_bp.route("/estado/<int:ot_id>", methods=["POST"])
@require_operativo_o_admin
def cambiar_estado(ot_id):
    ot = OrdenTrabajo.query.get_or_404(ot_id)
    estado = request.form.get("estado")

    ot.estado = estado
    if estado == "completada":
        ot.fecha_cierre = datetime.utcnow()

    db.session.commit()

    flash("Estado actualizado.", "success")
    return redirect(url_for("ordenes.detalle_ot", ot_id=ot.id))

@ordenes_bp.route("/subir/<int:ot_id>", methods=["POST"])
@login_required
def subir_adjunto(ot_id):
    ot = OrdenTrabajo.query.get_or_404(ot_id)

    tipo = request.form.get("tipo")  # antes / despues
    archivo = request.files.get("archivo")

    if not archivo:
        flash("Debe seleccionar un archivo.", "danger")
        return redirect(url_for("ordenes.detalle_ot", ot_id=ot.id))

    # --------------------------
    # 📂 Crear carpeta de la OT
    # --------------------------
    upload_folder = os.path.join(
        current_app.root_path, "static", "uploads", f"ot_{ot.id}"
    )
    os.makedirs(upload_folder, exist_ok=True)

    # --------------------------
    # 🖼 Proceso de compresión
    # --------------------------
    img = Image.open(archivo)

    # Redimensionar para limitar ancho a 1600px
    max_width = 1600
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Convertir a RGB (evita problemas con PNG/transparencias)
    img = img.convert("RGB")

    # Guardar la imagen comprimida en buffer
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", optimize=True, quality=75)
    buffer.seek(0)

    # --------------------------
    # 📌 Asignar nombre archivo
    # --------------------------
    count = Adjunto.query.filter_by(orden_id=ot.id, tipo=tipo).count() + 1
    filename = f"ot_{ot.id}_{tipo}_{count}.jpg"
    filename = secure_filename(filename)

    filepath = os.path.join(upload_folder, filename)

    # Guardar físicamente el archivo
    with open(filepath, "wb") as f:
        f.write(buffer.read())

    # --------------------------
    # 💾 Guardar registro en DB
    # --------------------------
    adj = Adjunto(
        orden_id=ot.id,
        filename=filename,
        filepath=f"uploads/ot_{ot.id}/{filename}",
        tipo=tipo
    )

    db.session.add(adj)
    db.session.commit()

    flash("Archivo subido correctamente.", "success")
    return redirect(url_for("ordenes.detalle_ot", ot_id=ot.id))

@ordenes_bp.route("/modal_subir/<int:ot_id>/<tipo>")
@login_required
def modal_subir_adjunto(ot_id, tipo):
    ot = OrdenTrabajo.query.get_or_404(ot_id)
    return render_template("ordenes/modal_subir_adjunto.html", ot=ot, tipo=tipo)

@ordenes_bp.route("/adjunto/eliminar/<int:adj_id>", methods=["POST"])
@login_required
def eliminar_adjunto(adj_id):
    adj = Adjunto.query.get_or_404(adj_id)

    # Ruta física
    filepath = os.path.join(current_app.root_path, "static", adj.filepath)

    # Borrar archivo físico
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print("Error borrando archivo:", e)

    # Borrar registro
    ot_id = adj.orden_id
    db.session.delete(adj)
    db.session.commit()

    flash("Adjunto eliminado correctamente.", "success")
    return redirect(url_for("ordenes.detalle_ot", ot_id=ot_id))

@ordenes_bp.route("/mis-ordenes")
@require_tecnico
def mis_ordenes():
    ordenes = OrdenTrabajo.query.filter_by(tecnico_id=current_user.id).all()
    return render_template("ordenes/mis_ordenes.html", ordenes=ordenes)
