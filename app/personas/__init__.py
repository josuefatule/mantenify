from flask import Blueprint

personas_bp = Blueprint(
    "personas",
    __name__,
    template_folder="../templates/personas"
)

from . import routes
