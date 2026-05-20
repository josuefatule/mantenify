import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
from flask_mail import Mail

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor inicia sesión para continuar."

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    # Registrar modelos
    from app import models  # noqa: F401

    # Registrar blueprints
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.proyectos.routes import proyectos_bp
    from app.unidades.routes import unidades_bp
    from app.activos.routes import activos_bp
    from app.solicitudes.routes import solicitudes_bp
    from app.ordenes import ordenes_bp
    from app.cuotas import cuotas_bp
    from app.personas import personas_bp
    from app.finanzas import finanzas_bp
    from app.reportes import reportes_bp
    from app.etapas import etapas_bp
    from app.comunicaciones import comunicaciones_bp

    app.register_blueprint(proyectos_bp)
    app.register_blueprint(unidades_bp)
    app.register_blueprint(activos_bp)
    app.register_blueprint(solicitudes_bp)
    app.register_blueprint(ordenes_bp)
    app.register_blueprint(cuotas_bp)
    app.register_blueprint(personas_bp)
    app.register_blueprint(finanzas_bp, url_prefix="/finanzas")
    app.register_blueprint(reportes_bp)
    app.register_blueprint(etapas_bp)
    app.register_blueprint(comunicaciones_bp)
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))
