from flask_mail import Message
from flask import current_app

from app import mail


def enviar_correo(
    asunto,
    destinatarios,
    cuerpo,
    html=None,
    adjuntos=None
):
    """
    Servicio reutilizable de envío de correos.
    """

    msg = Message(
        subject=asunto,
        recipients=destinatarios,
        body=cuerpo,
        html=html
    )

    # Adjuntos opcionales
    if adjuntos:
        for adjunto in adjuntos:

            msg.attach(
                filename=adjunto["filename"],
                content_type=adjunto["content_type"],
                data=adjunto["data"]
            )

    mail.send(msg)