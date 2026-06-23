from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from datetime import date

from core.models import Agent
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.week_utils import (
    parse_semaine,
    date_to_week_string,
)
from surveillance.services.detail_superviseur_service import DetailSuperviseurService


class DetailSuperviseurView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/superviseur/detail_superviseur.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        superviseur = get_object_or_404(
            Agent,
            pk=self.kwargs["pk"]
        )

        # Semaine sélectionnée
        debut_date = parse_semaine(self.request.GET.get("semaine"))

        context.update(
            DetailSuperviseurService.get_data(superviseur, debut_semaine=debut_date)
        )

        today = date.today()
        context.update({
            "semaine_selectionnee": date_to_week_string(debut_date),
            "semaine_max": date_to_week_string(today),
        })

        return context