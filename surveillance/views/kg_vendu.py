from django.views.generic import TemplateView
from datetime import date

from core.models import Produit, Agent
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.week_utils import (
    parse_semaine,
    fin_semaine,
    date_to_week_string,
)
from surveillance.services.liste_kg_service import (
    ListeKgVenduService
)


class ListeKgVenduView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/kg_vendu/liste_kg_vendu.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Semaine sélectionnée
        debut_date = parse_semaine(self.request.GET.get("semaine"))
        fin_date = fin_semaine(debut_date)

        superviseur = self.request.GET.get("superviseur")
        produit = self.request.GET.get("produit")

        superviseur = int(superviseur) if superviseur else None
        produit = int(produit) if produit else None

        # Données sur la semaine sélectionnée
        kpis = ListeKgVenduService.get_kpis(debut_date, fin_date)
        superviseurs_stats = ListeKgVenduService.get_superviseurs(debut_date, fin_date)
        agents_stats = ListeKgVenduService.get_agents(
            debut_date,
            fin_date,
            superviseur=superviseur,
            produit=produit
        )

        today = date.today()

        context.update({
            "kpis": kpis,
            "superviseurs_stats": superviseurs_stats,
            "agents_stats": agents_stats,
            "superviseurs": Agent.objects.filter(
                type_agent="entrepot",
                est_actif=True
            ),
            "produits": Produit.objects.all(),
            "selected_superviseur": superviseur,
            "selected_produit": produit,
            "semaine_selectionnee": date_to_week_string(debut_date),
            "semaine_max": date_to_week_string(today),
        })

        return context