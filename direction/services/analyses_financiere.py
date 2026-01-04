from decimal import Decimal
from django.db.models import Sum, F

from core.models import Vente, Agent, LotEntrepot, Fournisseur

DEC_ZERO = Decimal("0.00")


class PilotageGlobalService:
    """
    Pilotage financier global – Direction
    """

    @staticmethod
    def get_kpis_globaux(date_debut, date_fin):
        ca_global = Vente.objects.filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False
        ).aggregate(
            total=Sum(F("quantite") * F("prix_vente_unitaire"))
        )["total"] or DEC_ZERO

        return {
            "ca_global": ca_global,
        }

    @staticmethod
    def get_superviseurs():
        superviseurs = Agent.objects.filter(type_agent="entrepot")

        data = []
        for sup in superviseurs:
            data.append({
                "superviseur": sup,
                # ⬇️ ON UTILISE TES PROPRIÉTÉS (SOURCE DE VÉRITÉ)
                "solde": sup.solde_reel_superviseur,
                "depenses": sup.total_depenses_superviseur,
                "versements": sup.total_versements_vente,
            })

        return data

    @staticmethod
    def get_fournisseurs(date_debut, date_fin):
        fournisseurs = Fournisseur.objects.all()

        data = []
        for f in fournisseurs:
            data.append({
                "fournisseur": f,
                "dette_contractuelle": LotEntrepot.objects.filter(
                    fournisseur=f
                ).aggregate(
                    total=Sum(F("quantite_initiale") * F("prix_achat_unitaire"))
                )["total"] or DEC_ZERO,
                # ⬇️ TA LOGIQUE EXISTANTE
                "dette_consommee": f.get_dette_actuelle(
                    date_debut=date_debut,
                    date_fin=date_fin
                ),
            })

        return data
