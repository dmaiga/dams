from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from datetime import date

from core.models import Produit
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.week_utils import (
    parse_semaine,
    date_to_week_string,
    qs_semaine,
    parse_mois,
    date_to_month_string,
    qs_mois,
)
from surveillance.services.detail_produit_service import DetailProduitService


class DetailProduitView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/produits/detail_produit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        produit = get_object_or_404(
            Produit,
            pk=self.kwargs["pk"]
        )

        origine = self.request.GET.get("from", "kg")
        periode = self.request.GET.get("periode", "semaine")
        if periode not in ("semaine", "mois"):
            periode = "semaine"

        today = date.today()

        if periode == "mois":
            debut_mois = parse_mois(self.request.GET.get("mois"))
            context.update(
                DetailProduitService.get_data(produit, debut_mois=debut_mois, periode="mois")
            )
            mois_selectionne = date_to_month_string(debut_mois)
            semaine_selectionnee = None
            qs_periode = qs_mois(mois_selectionne)
        else:
            debut_semaine = parse_semaine(self.request.GET.get("semaine"))
            context.update(
                DetailProduitService.get_data(produit, debut_semaine=debut_semaine, periode="semaine")
            )
            semaine_selectionnee = date_to_week_string(debut_semaine)
            mois_selectionne = None
            qs_periode = qs_semaine(semaine_selectionnee)

        context.update({
            "periode": periode,
            "semaine_selectionnee": semaine_selectionnee,
            "semaine_max": date_to_week_string(today),
            "mois_selectionne": mois_selectionne,
            "mois_max": date_to_month_string(today),
            "qs_semaine": qs_periode,
            "origine": origine,
            "theme": origine,
        })

        return context
