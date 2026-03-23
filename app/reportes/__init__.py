from flask import Blueprint

reportes_bp = Blueprint(
    "reportes",
    __name__,
    url_prefix="/reportes"   # templates NO van aquí
)

from . import routes
