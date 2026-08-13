from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from datetime import date

from core.models import Agent, Produit
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.week_utils import (
    parse_semaine,
    date_to_week_string,
    qs_semaine,
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
        origine = self.request.GET.get("from", "kg")

        produit_id = self.request.GET.get("produit")
        produit_id = int(produit_id) if produit_id else None
        produit = Produit.objects.filter(pk=produit_id).first() if produit_id else None

        context.update(
            DetailSuperviseurService.get_data(superviseur, debut_semaine=debut_date, produit=produit)
        )

        today = date.today()
        context.update({
            "semaine_selectionnee": date_to_week_string(debut_date),
            "semaine_max": date_to_week_string(today),
            "qs_semaine": qs_semaine(date_to_week_string(debut_date)),
            "origine": origine,
            "theme": origine,
            "produits": Produit.objects.all(),
            "selected_produit": produit_id,
        })

        return context
