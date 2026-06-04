# services/alertes/solde.py

from decimal import Decimal
from agents.services.superviseur_service import SuperviseurDashboardService
from core.models import Alerte,RecouvrementSuperviseur
# services/alertes/solde.py

from decimal import Decimal
from datetime import timedelta
from django.utils.timezone import now
# services/alertes/solde.py

from decimal import Decimal
from django.utils.timezone import now

from core.models import (
    Alerte,
    RecouvrementSuperviseur
)


class SoldeAlertService:

    @staticmethod
    def check_superviseur_solde(superviseur):

        # =====================================================
        # CASH RÉEL OPÉRATIONNEL
        # =====================================================

        cash = superviseur.solde_operationnel_superviseur

        # Rien à signaler
        if cash <= 0:
            return Decimal("0.00")

        # =====================================================
        # DERNIER VERSEMENT
        # =====================================================

        dernier_versement = (
            RecouvrementSuperviseur.objects
            .filter(superviseur=superviseur)
            .order_by("-date_recouvrement")
            .first()
        )

        if dernier_versement:
            jours_sans_versement = (
                now() - dernier_versement.date_recouvrement
            ).days
        else:
            jours_sans_versement = 999

        # =====================================================
        # ALERTES TEMPORELLES
        # =====================================================

        if jours_sans_versement >= 2:

            SoldeAlertService._create_alert(
                superviseur=superviseur,
                cash=cash,
                niveau="critique",
                message="Cash détenu sans versement depuis plus de 48h"
            )

        elif jours_sans_versement >= 1:

            SoldeAlertService._create_alert(
                superviseur=superviseur,
                cash=cash,
                niveau="warning",
                message="Cash détenu sans versement depuis 24h"
            )

        # =====================================================
        # ALERTES MONTANT
        # =====================================================

        if cash >= Decimal("100000"):

            SoldeAlertService._create_alert(
                superviseur=superviseur,
                cash=cash,
                niveau="critique",
                message="Solde superviseur très élevé"
            )

        elif cash >= Decimal("50000"):

            SoldeAlertService._create_alert(
                superviseur=superviseur,
                cash=cash,
                niveau="warning",
                message="Solde superviseur élevé"
            )

        return cash

    # =====================================================
    # CREATE ALERT
    # =====================================================

    @staticmethod
    def _create_alert(superviseur, cash, niveau, message):
    
        existe = Alerte.objects.filter(
            type_alerte="solde",
            superviseur=superviseur.user,
            message=message,
            est_vue=False
        ).exists()
    
        if existe:
            return
    
        Alerte.objects.create(
            type_alerte="solde",
            niveau=niveau,
            superviseur=superviseur.user,
            message=f"{message} : {cash} FCFA"
        )
        