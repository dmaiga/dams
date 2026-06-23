from django.views.generic import TemplateView
from datetime import date, timedelta

from surveillance.mixins import SurveillanceAccessMixin
from surveillance.week_utils import (
    parse_semaine,
    fin_semaine,
    semaine_precedente,
    date_to_week_string,
)

from surveillance.services.vente_service import VenteSurveillanceService
from surveillance.services.prix_service import PrixSurveillanceService
from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService,
)
from surveillance.services.superviseur_service import SuperviseurSurveillanceService
from surveillance.services.produit_service import ProduitSurveillanceService


class DashboardSurveillanceView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/dashboard_surveillance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Semaine sélectionnée
        debut_date = parse_semaine(self.request.GET.get("semaine"))
        fin_date = fin_semaine(debut_date)
        debut_prec, fin_prec = semaine_precedente(debut_date)

        # Calcul des volumes de la semaine sélectionnée
        kg_semaine = VenteSurveillanceService.kg_vendus(debut_date, fin_date)
        kg_semaine_prec = VenteSurveillanceService.kg_vendus(debut_prec, fin_prec)
        variation = ComparaisonService.variation(kg_semaine, kg_semaine_prec)

        # Période mois
        debut_mois, fin_mois = ComparaisonPeriodeService.mois_actuel()
        kg_mois = VenteSurveillanceService.kg_vendus(debut_mois, fin_mois)
        debut_mois_prec, fin_mois_prec = ComparaisonPeriodeService.mois_precedent()
        kg_mois_prec = VenteSurveillanceService.kg_vendus(debut_mois_prec, fin_mois_prec)
        variation_mois = ComparaisonService.variation(kg_mois, kg_mois_prec)

        # Ventes rouges optimisées (Slicing au niveau SQL via limit)
        ventes_rouges = PrixSurveillanceService.ventes_a_perte(limit=10)
        nb_produits_rouges = PrixSurveillanceService.count_anomalies()

        # Variations spécifiques de la semaine sélectionnée
        superviseurs = SuperviseurSurveillanceService.variations_semaine(debut_semaine=debut_date)
        produits = ProduitSurveillanceService.variations_semaine(debut_semaine=debut_date)

        today = date.today()

        context.update({
            "kg_semaine": kg_semaine,
            "kg_semaine_prec": kg_semaine_prec,
            "variation": round(variation, 2),

            "kg_mois": kg_mois,
            "kg_mois_prec": kg_mois_prec,
            "variation_mois": round(variation_mois, 2),

            "nb_produits_rouges": nb_produits_rouges,
            "ventes_rouges": ventes_rouges,

            "superviseurs_surveillance": superviseurs[:5],
            "produits_surveillance": produits[:5],

            "semaine_selectionnee": date_to_week_string(debut_date),
            "semaine_max": date_to_week_string(today),
        })

        return context