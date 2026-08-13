from django.views.generic import TemplateView
from datetime import date

from core.models import Produit, Agent
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.services.comparaison_service import ComparaisonPeriodeService
from surveillance.week_utils import (
    parse_semaine,
    fin_semaine,
    date_to_week_string,
    qs_semaine,
    parse_mois,
    date_to_month_string,
    qs_mois,
)
from surveillance.services.liste_kg_service import (
    ListeKgVenduService
)


class ListeKgVenduView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/kg_vendu/liste_kg_vendu.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        periode = self.request.GET.get("periode", "semaine")
        if periode not in ("semaine", "mois"):
            periode = "semaine"

        today = date.today()

        if periode == "mois":
            debut_mois = parse_mois(self.request.GET.get("mois"))
            debut_date, fin_date = ComparaisonPeriodeService.mois(debut_mois)
            mois_selectionne = date_to_month_string(debut_mois)
            semaine_selectionnee = None
            qs_periode = qs_mois(mois_selectionne)
        else:
            debut_date = parse_semaine(self.request.GET.get("semaine"))
            fin_date = fin_semaine(debut_date)
            semaine_selectionnee = date_to_week_string(debut_date)
            mois_selectionne = None
            qs_periode = qs_semaine(semaine_selectionnee)

        superviseur = self.request.GET.get("superviseur")
        produit = self.request.GET.get("produit")

        superviseur = int(superviseur) if superviseur else None
        produit = int(produit) if produit else None

        # Données sur la période sélectionnée
        kpis = ListeKgVenduService.get_kpis(debut_date, fin_date)
        superviseurs_stats = ListeKgVenduService.get_superviseurs(debut_date, fin_date)
        agents_stats = ListeKgVenduService.get_agents(
            debut_date,
            fin_date,
            superviseur=superviseur,
            produit=produit
        )

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
            "periode": periode,
            "semaine_selectionnee": semaine_selectionnee,
            "semaine_max": date_to_week_string(today),
            "mois_selectionne": mois_selectionne,
            "mois_max": date_to_month_string(today),
            "theme": "kg",
            "qs_semaine": qs_periode,
        })

        return context
