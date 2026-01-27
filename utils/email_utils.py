from django.core.mail import EmailMessage
from django.conf import settings
import os


def envoyer_rapport_email(fichier_path, sujet, message, destinataires):
    email = EmailMessage(
        subject=sujet,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinataires,
    )

    if fichier_path and os.path.exists(fichier_path):
        email.attach_file(fichier_path)

    email.send()
