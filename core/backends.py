from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from core.models import Agent  # adapte selon ton app

class TelephoneBackend(ModelBackend):
    """
    Permet la connexion via le numéro de téléphone au lieu du username
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # On suppose que chaque Agent a un user lié
            agent = Agent.objects.select_related('user').get(telephone=username)
            user = agent.user
        except Agent.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None
