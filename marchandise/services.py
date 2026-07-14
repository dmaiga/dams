"""Services metier de l'application marchandise."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from core.models import (
    AffectationLotSuperviseur,
    DetailDistribution,
    DistributionAgent,
    LotEntrepot,
    Vente,
)


_NON_RENSEIGNE = object()


class AffectationLotService:
    """Operations de correction administrative des affectations de lots."""

    _QUANTITE_MAX = Decimal("99999999.99")

    @classmethod
    def corriger_affectation(
        cls,
        affectation_id,
        *,
        quantite=_NON_RENSEIGNE,
        date_affectation=_NON_RENSEIGNE,
    ):
        """Corrige les champs administratifs d'une affectation.

        La quantite rejoue, en mise a jour, les ecritures faites a la creation :
        lot, affectation et, pour une distribution directe, sa distribution et
        son detail. La date n'a aucun impact sur les quantites.
        """
        quantite = cls._normaliser_quantite(quantite)
        date_affectation = cls._normaliser_date(date_affectation)

        with transaction.atomic():
            affectation = AffectationLotSuperviseur.objects.select_for_update().get(
                pk=affectation_id
            )
            lot = LotEntrepot.objects.select_for_update().get(pk=affectation.lot_id)
            distribution_directe = detail_direct = None
            if quantite is not _NON_RENSEIGNE and quantite != affectation.quantite_initiale:
                distribution_directe, detail_direct = cls._charger_distribution_directe(
                    affectation,
                    verrouiller=True,
                )
            corrections = cls._preparer_correction(
                affectation,
                lot,
                quantite=quantite,
                date_affectation=date_affectation,
                distribution_directe=distribution_directe,
                detail_direct=detail_direct,
            )

            if "quantite_initiale" in corrections:
                affectation.quantite_initiale = corrections["quantite_initiale"]
                affectation.quantite_restante = corrections["quantite_restante_affectation"]
                affectation.save(
                    update_fields=["quantite_initiale", "quantite_restante"]
                )

                lot.quantite_restante = corrections["quantite_restante_lot"]
                lot.quantite_disponible_rot = corrections["quantite_disponible_rot"]
                lot.save(update_fields=["quantite_restante", "quantite_disponible_rot"])

                if detail_direct:
                    detail_direct.quantite = corrections["quantite_detail_distribution"]
                    detail_direct.save(update_fields=["quantite"])

                    distribution_directe.quantite_totale = corrections[
                        "quantite_distribution"
                    ]
                    distribution_directe.save(update_fields=["quantite_totale"])

            if "date_affectation" in corrections:
                affectation.date_affectation = corrections["date_affectation"]
                affectation.save(update_fields=["date_affectation"])

        return affectation

    @classmethod
    def valider_correction_affectation(
        cls,
        affectation_id,
        *,
        quantite=_NON_RENSEIGNE,
        date_affectation=_NON_RENSEIGNE,
    ):
        """Valide une correction sans ecrire, pour les interfaces utilisatrices."""
        quantite = cls._normaliser_quantite(quantite)
        date_affectation = cls._normaliser_date(date_affectation)
        affectation = AffectationLotSuperviseur.objects.select_related("lot").get(
            pk=affectation_id
        )
        distribution_directe = detail_direct = None
        if quantite is not _NON_RENSEIGNE and quantite != affectation.quantite_initiale:
            distribution_directe, detail_direct = cls._charger_distribution_directe(
                affectation,
                verrouiller=False,
            )
        cls._preparer_correction(
            affectation,
            affectation.lot,
            quantite=quantite,
            date_affectation=date_affectation,
            distribution_directe=distribution_directe,
            detail_direct=detail_direct,
        )

    @classmethod
    def _preparer_correction(
        cls,
        affectation,
        lot,
        *,
        quantite,
        date_affectation,
        distribution_directe,
        detail_direct,
    ):
        corrections = {}

        if quantite is not _NON_RENSEIGNE and quantite != affectation.quantite_initiale:
            difference = quantite - affectation.quantite_initiale
            quantite_restante_lot = lot.quantite_restante - difference
            quantite_disponible_rot = lot.quantite_disponible_rot + difference

            if quantite_restante_lot < Decimal("0.00"):
                raise ValidationError(
                    "Stock central insuffisant pour augmenter cette affectation. "
                    f"Disponible : {lot.quantite_restante}."
                )
            if quantite_restante_lot > lot.quantite_initiale:
                raise ValidationError(
                    "La correction restituerait plus de stock que la quantite "
                    "initiale du lot."
                )
            if quantite_disponible_rot < Decimal("0.00"):
                raise ValidationError(
                    "La correction rendrait la quantite disponible pour le ROT "
                    "negative."
                )

            if detail_direct:
                quantite_vendue = (
                    Vente.objects.filter(
                        detail_distribution=detail_direct,
                        est_supprime=False,
                    ).aggregate(total=Sum("quantite"))["total"]
                    or Decimal("0.00")
                )
                if quantite < quantite_vendue:
                    raise ValidationError(
                        "La quantite corrigee ne peut pas etre inferieure aux "
                        f"ventes deja enregistrees ({quantite_vendue})."
                    )

                # La creation directe vide immediatement le stock virtuel du
                # superviseur et alimente exactement un detail de distribution.
                quantite_restante_affectation = Decimal("0.00")
            else:
                # Pour une affectation pas encore distribuee directement, on
                # conserve la quantite deja sortie du solde du superviseur.
                quantite_restante_affectation = affectation.quantite_restante + difference
                if quantite_restante_affectation < Decimal("0.00"):
                    raise ValidationError(
                        "La correction est inferieure a la quantite deja sortie "
                        "de cette affectation."
                    )
                if quantite_restante_affectation > quantite:
                    raise ValidationError(
                        "La quantite restante de l'affectation depasserait sa "
                        "quantite initiale corrigee."
                    )

            corrections.update(
                quantite_initiale=quantite,
                quantite_restante_affectation=quantite_restante_affectation,
                quantite_restante_lot=quantite_restante_lot,
                quantite_disponible_rot=quantite_disponible_rot,
            )
            if detail_direct:
                corrections.update(
                    quantite_detail_distribution=quantite,
                    # Le formulaire cree un seul detail, mais un recalcul
                    # protege aussi les distributions qui auraient recu des
                    # details supplementaires apres leur creation.
                    quantite_distribution=(
                        DetailDistribution.objects.filter(
                            distribution=distribution_directe
                        ).aggregate(total=Sum("quantite"))["total"]
                        - detail_direct.quantite
                        + quantite
                    ),
                )

        if (
            date_affectation is not _NON_RENSEIGNE
            and date_affectation != affectation.date_affectation
        ):
            corrections["date_affectation"] = date_affectation

        return corrections

    @staticmethod
    def _charger_distribution_directe(affectation, *, verrouiller):
        """Retrouve le couple distribution/detail cree pour une affectation directe.

        Le schema ne relie pas directement une affectation a une distribution.
        La cle metier existante est donc le lot et le couple superviseur/agent
        conserve dans ``agent_terrain_direct``. Plusieurs correspondances ne
        permettent pas une correction fiable : on refuse alors la modification
        plutot que d'alterer une autre distribution.
        """
        if not affectation.agent_terrain_direct_id:
            return None, None

        details = DetailDistribution.objects.filter(
            lot_id=affectation.lot_id,
            distribution__superviseur_id=affectation.superviseur_id,
            distribution__agent_terrain_id=affectation.agent_terrain_direct_id,
        )
        if verrouiller:
            details = details.select_for_update()
        details = list(details)

        if len(details) != 1:
            raise ValidationError(
                "Impossible d'identifier de maniere unique la distribution "
                "directe liee a cette affectation."
            )

        distribution_query = DistributionAgent.objects
        if verrouiller:
            distribution_query = distribution_query.select_for_update()
        distribution = distribution_query.get(pk=details[0].distribution_id)
        return distribution, details[0]

    @classmethod
    def _normaliser_quantite(cls, valeur):
        if valeur is _NON_RENSEIGNE:
            return valeur

        try:
            quantite = Decimal(str(valeur))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(
                "La quantite corrigee doit etre un nombre decimal valide."
            ) from exc

        if not quantite.is_finite() or quantite <= Decimal("0.00"):
            raise ValidationError("La quantite corrigee doit etre strictement positive.")
        if quantite.as_tuple().exponent < -2:
            raise ValidationError(
                "La quantite corrigee ne peut pas avoir plus de deux decimales."
            )
        if quantite > cls._QUANTITE_MAX:
            raise ValidationError("La quantite corrigee depasse la valeur maximale autorisee.")

        return quantite.quantize(Decimal("0.01"))

    @staticmethod
    def _normaliser_date(valeur):
        if valeur is _NON_RENSEIGNE:
            return valeur
        if isinstance(valeur, datetime):
            return valeur.date()
        if not isinstance(valeur, date):
            raise ValidationError("La date d'affectation corrigee est invalide.")
        return valeur
