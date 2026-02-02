# core/services/superviseur_analysis_service.py

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Sum, F
from django.db.models.functions import Coalesce

from core.models import (
    Agent,
    Vente,
    Recouvrement,
    RecouvrementSuperviseur,
    VersementBancaire,
    Depense,
    ClotureMensuelle,
)


class SuperviseurAnalysisService:
    """
    Service DIRECTIONNEL
    Calcul ABSOLU basé UNIQUEMENT sur les clôtures.
    """

    # =====================================================
    # UTILITAIRE CENTRAL
    # =====================================================
    @staticmethod
    def get_periode_ouverte(superviseur):
        """
        Détermine la période ouverte réelle d'un superviseur.
        """
        cloture = (
            ClotureMensuelle.objects
            .filter(superviseur=superviseur, est_cloture=True)
            .order_by('-date_fin_periode')
            .first()
        )

        if cloture:
            date_debut = cloture.date_fin_periode + timedelta(days=1)
            solde_ouverture = cloture.solde_cloture
            cloture_ref = cloture
        else:
            date_debut = date.min
            solde_ouverture = Decimal("0.00")
            cloture_ref = None

        date_fin = timezone.now().date()

        return date_debut, date_fin, solde_ouverture, cloture_ref

    # =====================================================
    # SUPERVISEURS – FINANCE (POST-CLÔTURE)
    # =====================================================
    @staticmethod
    def get_superviseurs_finance():
        data = []

        superviseurs = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        )

        for sup in superviseurs:
            (
                date_debut,
                date_fin,
                solde_ouverture,
                cloture_ref
            ) = SuperviseurAnalysisService.get_periode_ouverte(sup)

            ventes_perso = Vente.objects.filter(
                agent=sup,
                date_vente__date__gte=date_debut,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0.00")
                )
            )["total"]

            ventes_agents = Vente.objects.filter(
                agent__superviseur=sup,
                agent__type_agent__in=["terrain", "agent_gros"],
                date_vente__date__gte=date_debut,
                est_supprime=False
            ).aggregate(
                total=Coalesce(
                    Sum(F("quantite") * F("prix_vente_unitaire")),
                    Decimal("0.00")
                )
            )["total"]

            recouvre_agents = Recouvrement.objects.filter(
                superviseur=sup,
                date_recouvrement__date__gte=date_debut
            ).aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
            )["total"]

            remis_rot = RecouvrementSuperviseur.objects.filter(
                superviseur=sup,
                date_recouvrement__date__gte=date_debut
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0.00"))
            )["total"]

            montant_chez_agents = max(
                ventes_agents - recouvre_agents,
                Decimal("0.00")
            )

            solde_superviseur = (
                solde_ouverture
                + ventes_perso
                + recouvre_agents
                - remis_rot
            )

            data.append({
                "superviseur": sup,

                # référence comptable
                "cloture_reference": cloture_ref,
                "periode_debut": date_debut,
                "periode_fin": date_fin,
                "solde_ouverture": solde_ouverture,

                # flux post-clôture
                "ventes_perso": ventes_perso,
                "ventes_agents": ventes_agents,
                "recouvre_agents": recouvre_agents,
                "montant_chez_agents": montant_chez_agents,
                "remis_rot": remis_rot,

                # situation actuelle
                "solde_superviseur": solde_superviseur,
            })

        return data

    # =====================================================
    # ROT – FINANCE (POST-CLÔTURE)
    # =====================================================
    @staticmethod
    def get_rots_finance():
        data = []

        rots = Agent.objects.filter(
            type_agent='rot',
            est_actif=True
        )

        for rot in rots:
            recu_superviseurs = RecouvrementSuperviseur.objects.filter(
                rot=rot
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0.00"))
            )["total"]

            verse_banque = VersementBancaire.objects.filter(
                effectue_par=rot
            ).aggregate(
                total=Coalesce(Sum("montant_vente"), Decimal("0.00"))
            )["total"]

            depenses = Depense.objects.filter(
                effectue_par=rot
            ).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0.00"))
            )["total"]

            solde_rot = recu_superviseurs - verse_banque - depenses

            data.append({
                "rot": rot,
                "recouvre": recu_superviseurs,
                "verse_banque": verse_banque,
                "depenses": depenses,
                "solde": solde_rot,
            })

        return data
