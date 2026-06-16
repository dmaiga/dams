from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta


class ComparaisonPeriodeService:
    @staticmethod
    def semaine_actuelle():
        today = timezone.now().date()

        debut = today - timedelta(days=today.weekday())
        fin = debut + timedelta(days=6)

        return debut, fin

    @staticmethod
    def semaine_precedente():
        debut, fin = (
            ComparaisonPeriodeService.semaine_actuelle()
        )

        return (
            debut - timedelta(days=7),
            fin - timedelta(days=7)
        )

    @staticmethod
    def mois_actuel():
        today = timezone.now().date()

        debut = today.replace(day=1)

        prochain_mois = debut + relativedelta(months=1)
        fin = prochain_mois - timedelta(days=1)

        return debut, fin

    @staticmethod
    def mois_precedent():

        debut_actuel, _ = (
            ComparaisonPeriodeService.mois_actuel()
        )

        debut_prec = debut_actuel - relativedelta(months=1)

        fin_prec = debut_actuel - timedelta(days=1)

        return debut_prec, fin_prec
    
class ComparaisonService:
    @staticmethod
    def variation(valeur_actuelle, valeur_reference):
        if not valeur_reference:
            return Decimal("0")
        return (
            (
                valeur_actuelle
                - valeur_reference
            )
            / valeur_reference
        ) * 100