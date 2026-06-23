from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
from dateutil.relativedelta import relativedelta


class ComparaisonPeriodeService:
    @staticmethod
    def semaine(debut):
        return debut, debut + timedelta(days=6)

    @staticmethod
    def semaine_prec(debut):
        prec = debut - timedelta(days=7)
        return prec, prec + timedelta(days=6)

    @staticmethod
    def semaine_actuelle():
        today = timezone.now().date()

        debut = today - timedelta(days=today.weekday())
        return ComparaisonPeriodeService.semaine(debut)

    @staticmethod
    def semaine_precedente():
        debut, _ = ComparaisonPeriodeService.semaine_actuelle()
        return ComparaisonPeriodeService.semaine_prec(debut)

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