from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, timedelta
from django.utils import timezone

from paie.services.salaire_liste_service import SalaireListeService


class SalaireLectureView(LoginRequiredMixin, TemplateView):
    template_name = "paie/salaire_liste.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ----------------------------
        # PÉRIODE
        # ----------------------------
        periode = self.request.GET.get("periode", "mensuel")
        today = timezone.now().date()

        if periode == "custom":
            date_debut = self.request.GET.get("date_debut")
            date_fin = self.request.GET.get("date_fin")

            if date_debut and date_fin:
                date_debut = datetime.strptime(date_debut, "%Y-%m-%d").date()
                date_fin = datetime.strptime(date_fin, "%Y-%m-%d").date()
            else:
                date_debut = today.replace(day=1)
                date_fin = today

        else:  # mensuel par défaut
            date_debut = today.replace(day=1)
            date_fin = today

        # ----------------------------
        # SERVICE
        # ----------------------------
        result = SalaireListeService.get_salaires(date_debut, date_fin)

        context.update({
            "salaires": result["salaires"],
            "total_global": result["total_global"],
            "periode": periode,
            "date_debut": date_debut,
            "date_fin": date_fin,
        })

        return context
