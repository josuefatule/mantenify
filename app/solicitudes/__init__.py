from flask import Blueprint

solicitudes_bp = Blueprint("solicitudes", __name__, template_folder="templates")

from . import routes
