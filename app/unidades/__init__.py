from flask import Blueprint

unidades_bp = Blueprint("unidades", __name__, template_folder="templates")

from . import routes
