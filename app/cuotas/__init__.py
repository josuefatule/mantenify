from flask import Blueprint

cuotas_bp = Blueprint(
    "cuotas",
    __name__,
    url_prefix="/cuotas",
    template_folder="templates"
)

from . import routes
