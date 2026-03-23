from flask import Blueprint

ordenes_bp = Blueprint(
    "ordenes",
    __name__,
    url_prefix="/ordenes",
    template_folder="templates"
)

from . import routes
