"""Services metier de l'application marchandise."""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import (
    Agent,
    AffectationLotSuperviseur,
    DetailDistribution,
    DistributionAgent,
    Fournisseur,
    LotEntrepot,
    MouvementStock,
    Produit,
    Vente,
)
from core.services.lot_service import generer_reference_lot


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


class CessionReceptionService:
    """Reception d'une cession envoyee par l'app `cessions` de dams_champs
    (POST /api/cessions/), matérialisée comme un LotEntrepot de stock
    central — au meme titre qu'une reception manuelle via
    `core.forms.ReceptionLotForm` (marchandise/views.py::reception_lot).

    dams_champs reste la source de verite de la notion metier "cession" :
    ce service ne fait que projeter chaque cession recue en un LotEntrepot,
    sans recreer de notion parallele. Idempotent au niveau base de donnees
    via `LotEntrepot.cession_idempotency_key` (contrainte unique).
    """

    # Fournisseur dedie representant DAMS Agro / le champ, deja utilise
    # pour 36 lots existants a la decouverte du code (2026-08) — reutilise
    # tel quel plutot que d'introduire un nom concurrent.
    NOM_FOURNISSEUR_CHAMP = "Champ DAMS"

    # Agent de reception impose par le contrat métier (etape 6) : le
    # superviseur "entrepot" abdoulaye.kone, distinct de l'agent ROT
    # "kone.abdoulaye" — ne pas confondre les deux comptes.
    USERNAME_AGENT_RECEPTION = "abdoulaye.kone"

    @classmethod
    def recevoir_cession(cls, *, idempotency_key, produit_nom, quantite, prix_unitaire, date_cession):
        """Cree (ou retrouve) le LotEntrepot correspondant a une cession.

        Retourne un tuple (lot, cree) ou `cree` est False si un lot portant
        deja cette `idempotency_key` existait (cession retransmise).

        Leve ValidationError si le produit ou l'agent de reception sont
        introuvables — jamais de creation silencieuse de referentiel.
        """
        produit = cls._resoudre_produit(produit_nom)
        agent = cls._resoudre_agent_reception()
        fournisseur = cls._resoudre_fournisseur_champ()
        date_reception = cls._convertir_date_reception(date_cession)

        try:
            with transaction.atomic():
                lot = LotEntrepot.objects.create(
                    produit=produit,
                    fournisseur=fournisseur,
                    quantite_initiale=quantite,
                    quantite_restante=quantite,
                    prix_achat_unitaire=prix_unitaire,
                    date_reception=date_reception,
                    receptionne_par=agent,
                    reference_lot=generer_reference_lot(),
                    cession_idempotency_key=idempotency_key,
                )
                # Meme invariant que ReceptionLotForm.save() : toute
                # reception de lot cree systematiquement son mouvement
                # d'entree — voir marchandise/APP_MARCHANDISE.md.
                MouvementStock.objects.create(
                    produit=lot.produit,
                    lot=lot,
                    type_mouvement='RECEPTION',
                    quantite=lot.quantite_initiale,
                    date_mouvement=lot.date_reception,
                )
        except IntegrityError:
            # La contrainte unique sur cession_idempotency_key est la seule
            # garantie fiable en cas de requetes concurrentes portant la
            # meme cle — un simple if exists() prealable ne suffirait pas.
            lot = LotEntrepot.objects.filter(
                cession_idempotency_key=idempotency_key
            ).select_related('produit', 'fournisseur').first()
            if lot is None:
                raise
            return lot, False

        return lot, True

    @staticmethod
    def _resoudre_produit(produit_nom):
        try:
            return Produit.objects.get(nom__iexact=(produit_nom or '').strip())
        except Produit.DoesNotExist:
            raise ValidationError(
                f"Produit inconnu côté DAMS Distribution : « {produit_nom} ». "
                "Aucun Produit créé automatiquement — le référentiel produit "
                "doit exister prealablement (core.models.Produit)."
            )

    @classmethod
    def _resoudre_agent_reception(cls):
        try:
            return Agent.objects.select_related('user').get(
                user__username=cls.USERNAME_AGENT_RECEPTION
            )
        except Agent.DoesNotExist:
            raise ValidationError(
                "Agent de reception introuvable "
                f"(username={cls.USERNAME_AGENT_RECEPTION!r}). "
                "Precondition : ce compte doit exister dans dams avant toute "
                "reception de cession — aucune creation automatique."
            )

    @classmethod
    def _resoudre_fournisseur_champ(cls):
        fournisseur, _ = Fournisseur.objects.get_or_create(
            nom=cls.NOM_FOURNISSEUR_CHAMP
        )
        return fournisseur

    @staticmethod
    def _convertir_date_reception(date_cession):
        """Cession -> DateTimeField : minuit (heure du projet, UTC) le jour
        de la cession. Les lots recus manuellement portent l'heure reelle de
        saisie ; ceux issus d'une cession n'en ont pas — minuit est la
        convention la moins arbitraire pour une date sans heure source."""
        naive = datetime.combine(date_cession, time.min)
        return timezone.make_aware(naive) if timezone.is_naive(naive) else naive
