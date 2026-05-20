from flask import Blueprint

comunicaciones_bp = Blueprint(
    "comunicaciones",
    __name__
)

from . import routes