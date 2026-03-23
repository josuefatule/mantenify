from flask import Blueprint

activos_bp = Blueprint("activos", __name__, template_folder="templates")

from . import routes
