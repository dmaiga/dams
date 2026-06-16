from core.models import Agent
from surveillance.services.vente_service import (
    VenteSurveillanceService
)
from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService,
    ComparaisonService
)


class SuperviseurSurveillanceService:
    @staticmethod
    def variations_semaine():
        resultat = []
        debut_actuel, fin_actuel = (  ComparaisonPeriodeService.semaine_actuelle())
        debut_prec, fin_prec = ( ComparaisonPeriodeService.semaine_precedente() )
        superviseurs = Agent.objects.filter(type_agent="entrepot",est_actif=True )

        for superviseur in superviseurs:

            kg_actuel = (
                VenteSurveillanceService.kg_vendus(
                    debut_actuel,
                    fin_actuel,
                    superviseur=superviseur
                )
            )

            kg_prec = (
                VenteSurveillanceService.kg_vendus(
                    debut_prec,
                    fin_prec,
                    superviseur=superviseur
                )
            )

            variation = (
                ComparaisonService.variation(
                    kg_actuel,
                    kg_prec
                )
            )

            resultat.append({
                "superviseur": superviseur,
                "kg_actuel": kg_actuel,
                "kg_prec": kg_prec,
                "variation": round(variation, 2),
            })

        resultat.sort(
            key=lambda x: x["variation"]
        )

        return resultat