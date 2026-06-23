from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SurveillanceAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Mixin pour sécuriser les vues de l'application surveillance.
    Exige la connexion et limite l'accès aux superutilisateurs ou agents de type direction.
    """
    def test_func(self):
        return (
            self.request.user.is_authenticated and (
                self.request.user.is_superuser or (
                    hasattr(self.request.user, "agent") and 
                    self.request.user.agent.est_direction
                )
            )
        )
