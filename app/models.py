from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default="operativo")  # 'admin' o 'operativo'
    activo = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password) -> bool:
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.rol == "admin"

    def __repr__(self):
        return f"<User {self.email}>"
    
# ============================================================
# 🏢  PROYECTOS / RESIDENCIALES
# ============================================================
class Proyecto(db.Model):
    __tablename__ = "proyectos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    unidades = db.relationship("Unidad", backref="proyecto", lazy=True)

    def __repr__(self):
        return f"<Proyecto {self.nombre}>"

# ============================================================
# 🏘️  UNIDADES (Apt, casa, local)
# ============================================================
class Unidad(db.Model):
    __tablename__ = "unidades"
    __table_args__ = (
        db.UniqueConstraint('proyecto_id', 'nombre', name='uq_unidad_proyecto_nombre'),
    )
    id = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)
    etapa_id = db.Column(db.Integer, db.ForeignKey("etapas.id"), nullable=True)
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), nullable=True)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    activos = db.relationship("Activo", backref="unidad", lazy=True)
    cuotas = db.relationship("CuotaMantenimiento", backref="unidad", lazy=True)
    pagos = db.relationship("RegistroPago", backref="unidad", lazy=True)
    unidad_personas = db.relationship("UnidadPersona", backref="unidad", lazy=True)
    @property
    def esta_ocupada(self):
        return any(r.es_actual for r in self.unidad_personas)
    
    def __repr__(self):
        return f"<Unidad {self.nombre}>"

# ============================================================
# ⚙️  ACTIVOS (bombas, motores, cámaras, etc.)
# ============================================================
class Activo(db.Model):
    __tablename__ = "activos"

    id = db.Column(db.Integer, primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=False)

    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(100), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Activo {self.nombre}>"

# ============================================================
# 📥  SOLICITUDES DE MANTENIMIENTO
# ============================================================
class Solicitud(db.Model):
    __tablename__ = "solicitudes"
    id = db.Column(db.Integer, primary_key=True)
    # Relación jerárquica (correcto mantener los tres)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=False)
    activo_id = db.Column(db.Integer, db.ForeignKey("activos.id"), nullable=True)
    # Usuario que crea
    creado_por = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Información de la solicitud
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(30), default="pendiente")  # pendiente, en_proceso, cerrada
    prioridad = db.Column(db.String(20), default="media")  # baja, media, alta
    fecha_creada = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizada = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    # ---------------------------
    # RELACIONES REALES
    # ---------------------------
    proyecto_rel = db.relationship("Proyecto", backref="solicitudes")
    unidad_rel = db.relationship("Unidad", backref="solicitudes")
    activo_rel = db.relationship("Activo", backref="solicitudes")# Relación 1 a 1 con la Orden de Trabajo
    orden = db.relationship("OrdenTrabajo", backref="solicitud", uselist=False)
    def __repr__(self):
        return f"<Solicitud {self.titulo} ({self.estado})>"

# ============================================================
# 🛠️  ÓRDENES DE TRABAJO (OT)
# ============================================================
class OrdenTrabajo(db.Model):
    __tablename__ = "ordenes_trabajo"
    id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey("solicitudes.id"), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    tecnico = db.relationship("User", backref="ordenes_asignadas")  # ← AQUI
    estado = db.Column(db.String(30), default="asignada")
    # asignada, en_proceso, completada
    fecha_asignacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    notas = db.Column(db.Text, nullable=True)
    adjuntos = db.relationship("Adjunto", backref="orden", lazy=True)
    def __repr__(self):
        return f"<OT {self.id} - {self.estado}>"

# ============================================================
# 📸  ADJUNTOS (ANTES / DESPUÉS)
# ============================================================
class Adjunto(db.Model):
    __tablename__ = "adjuntos"

    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey("ordenes_trabajo.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)  # <--- nuevo
    tipo = db.Column(db.String(20), nullable=True)        # antes / despues
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Adjunto {self.filename}>"

# ============================================================
# 💵  CUOTA LITE (OBLIGACIÓN)
# ============================================================
class CuotaMantenimiento(db.Model):
    __tablename__ = "cuotas_mantenimiento"

    id = db.Column(db.Integer, primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=False)

    periodo = db.Column(db.Date, nullable=False)  # Ej: 2025-03-01 representa marzo 2025
    monto = db.Column(db.Numeric(10, 2), nullable=False)

    estado = db.Column(db.String(20), default="Pendiente")
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_pago = db.Column(db.DateTime, nullable=True)

    pago = db.relationship("RegistroPago", backref="cuota", uselist=False)

    def __repr__(self):
        return f"<Cuota {self.unidad_id} - {self.periodo}>"

# ============================================================
# 💳  REGISTRO DE PAGO (simple)
# ============================================================
class RegistroPago(db.Model):
    __tablename__ = "registro_pago"

    id = db.Column(db.Integer, primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=False)
    cuota_id = db.Column(db.Integer, db.ForeignKey("cuotas_mantenimiento.id"), nullable=False)

    monto_pagado = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)

    metodo_pago = db.Column(db.String(50), nullable=True)
    referencia = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Pago {self.monto_pagado} - cuota {self.cuota_id}>"

# ============================================================
# 🏗️  ETAPAS DEL PROYECTO
# ============================================================
class Etapa(db.Model):
    __tablename__ = "etapas"

    id = db.Column(db.Integer, primary_key=True)
    proyecto_id = db.Column(db.Integer, db.ForeignKey("proyectos.id"), nullable=False)

    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    monto_mantenimiento = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    # relación inversa (Proyecto → Etapas)
    proyecto = db.relationship("Proyecto", backref="etapas")
    # relación hacia unidades (todavía nullable hasta el paso 1.3)
    unidades = db.relationship("Unidad", backref="etapa", lazy=True)

    def __repr__(self):
        return f"<Etapa {self.nombre}>"

class Persona(db.Model):
    __tablename__ = "personas"

    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(150), nullable=False)
    identificacion = db.Column(db.String(50), nullable=True, unique=True)
    telefono = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    activo = db.Column(db.Boolean, default=True)

    relaciones = db.relationship("UnidadPersona", backref="persona", lazy=True)

    def __repr__(self):
        return f"<Persona {self.nombre_completo}>"

class UnidadPersona(db.Model):
    __tablename__ = "unidad_persona"

    id = db.Column(db.Integer, primary_key=True)

    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=False)
    persona_id = db.Column(db.Integer, db.ForeignKey("personas.id"), nullable=False)

    # 🔹 Aquí se indica si es propietario o inquilino
    es_propietario = db.Column(db.Boolean, nullable=False)  # "propietario" o "inquilino"

    es_principal = db.Column(db.Boolean, default=False)  # encargado oficial
    es_actual = db.Column(db.Boolean, default=True)

    fecha_desde = db.Column(db.Date, default=datetime.utcnow)
    fecha_hasta = db.Column(db.Date, nullable=True)

class Comunicacion(db.Model):
    __tablename__ = "comunicaciones"

    id = db.Column(db.Integer, primary_key=True)

    tipo = db.Column(db.String(30), nullable=False, default="individual")
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidades.id"), nullable=True)
    persona_id = db.Column(db.Integer, db.ForeignKey("personas.id"), nullable=True)
    enviado_por_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    email_destino = db.Column(db.String(150), nullable=False)
    asunto = db.Column(db.String(255), nullable=False)
    cuerpo = db.Column(db.Text, nullable=False)

    incluye_estado_cuenta = db.Column(db.Boolean, default=False)
    fecha_desde = db.Column(db.Date, nullable=True)
    fecha_hasta = db.Column(db.Date, nullable=True)

    estado = db.Column(db.String(30), default="enviada")  # enviada / error
    error = db.Column(db.Text, nullable=True)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    enviado_en = db.Column(db.DateTime, nullable=True)

    unidad = db.relationship("Unidad", backref="comunicaciones")
    persona = db.relationship("Persona", backref="comunicaciones")
    usuario = db.relationship("User", backref="comunicaciones_enviadas")