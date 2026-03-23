from flask import Blueprint

etapas_bp = Blueprint(
    "etapas",
    __name__,
    url_prefix="/etapas"
)

from . import routes
