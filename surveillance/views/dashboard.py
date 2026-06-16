from django.views.generic import TemplateView

from surveillance.services.vente_service import (VenteSurveillanceService)
from surveillance.services.prix_service import (PrixSurveillanceService)
from surveillance.services.comparaison_service import (
                                                        ComparaisonPeriodeService,ComparaisonService,
                                                       )

from surveillance.services.superviseur_service import (
    SuperviseurSurveillanceService
)

from surveillance.services.produit_service import (
    ProduitSurveillanceService
)

class DashboardSurveillanceView(TemplateView):
    template_name = (
        "surveillance/dashboard_surveillance.html"
    )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        debut_semaine, fin_semaine = (ComparaisonPeriodeService.semaine_actuelle() )
        debut_prec, fin_prec = ( ComparaisonPeriodeService.semaine_precedente())

        kg_semaine = ( VenteSurveillanceService.kg_vendus(debut_semaine,fin_semaine) )
        kg_semaine_prec = ( VenteSurveillanceService.kg_vendus(debut_prec,fin_prec) )

        variation = (ComparaisonService.variation(kg_semaine,kg_semaine_prec))

        debut_mois, fin_mois = ( ComparaisonPeriodeService.mois_actuel())

        kg_mois = ( VenteSurveillanceService.kg_vendus(debut_mois,fin_mois))
        debut_mois_prec, fin_mois_prec = (ComparaisonPeriodeService.mois_precedent() )
        kg_mois_prec = ( VenteSurveillanceService.kg_vendus(debut_mois_prec,fin_mois_prec) )

        variation_mois = ( ComparaisonService.variation(kg_mois,kg_mois_prec))
        
        ventes_rouges = (PrixSurveillanceService.ventes_a_perte())
        superviseurs = (
            SuperviseurSurveillanceService
            .variations_semaine()
        )

        produits = (
            ProduitSurveillanceService
            .variations_semaine()
        )
        context.update({
            "kg_semaine": kg_semaine,
            "kg_semaine_prec": kg_semaine_prec,
            "variation": round(variation, 2),

            "kg_mois": kg_mois,
            "kg_mois_prec": kg_mois_prec,
            "variation_mois": round(variation_mois, 2),
 
            "nb_produits_rouges": len(ventes_rouges),
            "ventes_rouges": ventes_rouges[:10],

            "superviseurs_surveillance": superviseurs[:5],
            "produits_surveillance": produits[:5],
        })

        return context