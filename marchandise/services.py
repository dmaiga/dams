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
from core.services.corrections import enregistrer_correction
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


class CorrectionLotService:
    """Correction administrative d'un LotEntrepot a la reception (sprint-13).

    Distinct de AffectationLotService.corriger_affectation : corrige le lot
    lui-meme (quantite initiale, prix d'achat, date de reception), pas une
    affectation deja sortie vers un superviseur. Accès reserve a la direction
    (mdmaiga) — voir direction.views._acces_admin_mdmaiga.
    """

    @classmethod
    def corriger_lot(
        cls,
        lot_id,
        *,
        quantite_initiale=_NON_RENSEIGNE,
        prix_achat_unitaire=_NON_RENSEIGNE,
        fournisseur=_NON_RENSEIGNE,
        date_reception=_NON_RENSEIGNE,
        motif='',
        utilisateur,
    ):
        motif = motif or ''

        quantite_initiale = AffectationLotService._normaliser_quantite(quantite_initiale)
        prix_achat_unitaire = cls._normaliser_prix(prix_achat_unitaire)

        with transaction.atomic():
            lot = LotEntrepot.objects.select_for_update().get(pk=lot_id)

            corrections_a_logger = []  # (type_correction, anciennes, nouvelles)

            if (
                quantite_initiale is not _NON_RENSEIGNE
                and quantite_initiale != lot.quantite_initiale
            ):
                quantite_sortie = lot.quantite_initiale - lot.quantite_restante
                if quantite_initiale < quantite_sortie:
                    raise ValidationError(
                        "La quantite corrigee est inferieure a ce qui a deja ete "
                        f"distribue depuis ce lot ({quantite_sortie})."
                    )
                ancienne_quantite = lot.quantite_initiale
                delta = quantite_initiale - lot.quantite_initiale
                lot.quantite_initiale = quantite_initiale
                lot.quantite_restante = lot.quantite_restante + delta
                corrections_a_logger.append((
                    'LOT_QUANTITE',
                    {'quantite_initiale': str(ancienne_quantite)},
                    {'quantite_initiale': str(quantite_initiale)},
                ))

            if (
                prix_achat_unitaire is not _NON_RENSEIGNE
                and prix_achat_unitaire != lot.prix_achat_unitaire
            ):
                ancien_prix = lot.prix_achat_unitaire
                lot.prix_achat_unitaire = prix_achat_unitaire
                corrections_a_logger.append((
                    'LOT_PRIX',
                    {'prix_achat_unitaire': str(ancien_prix)},
                    {'prix_achat_unitaire': str(prix_achat_unitaire)},
                ))

            if (
                fournisseur is not _NON_RENSEIGNE
                and fournisseur.pk != lot.fournisseur_id
            ):
                ancien_fournisseur = lot.fournisseur
                lot.fournisseur = fournisseur
                corrections_a_logger.append((
                    'LOT_FOURNISSEUR',
                    {
                        'fournisseur_id': ancien_fournisseur.id if ancien_fournisseur else None,
                        'fournisseur': ancien_fournisseur.nom if ancien_fournisseur else None,
                    },
                    {'fournisseur_id': fournisseur.id, 'fournisseur': fournisseur.nom},
                ))

            if (
                date_reception is not _NON_RENSEIGNE
                and date_reception != lot.date_reception
            ):
                ancienne_date = lot.date_reception
                lot.date_reception = date_reception
                corrections_a_logger.append((
                    'LOT_DATE',
                    {'date_reception': ancienne_date.isoformat()},
                    {'date_reception': date_reception.isoformat()},
                ))

            if not corrections_a_logger:
                return lot

            # save() recalcule valeur_stock_initiale et revalide les garde-fous
            # existants (quantite_restante <= quantite_initiale, etc.).
            lot.save()

            for type_correction, anciennes_valeurs, nouvelles_valeurs in corrections_a_logger:
                enregistrer_correction(
                    cible=lot,
                    type_correction=type_correction,
                    motif=motif,
                    utilisateur=utilisateur,
                    anciennes_valeurs=anciennes_valeurs,
                    nouvelles_valeurs=nouvelles_valeurs,
                )

        return lot

    @staticmethod
    def _normaliser_prix(valeur):
        if valeur is _NON_RENSEIGNE:
            return valeur
        try:
            prix = Decimal(str(valeur))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(
                "Le prix corrige doit etre un nombre decimal valide."
            ) from exc
        if not prix.is_finite() or prix <= Decimal("0.00"):
            raise ValidationError("Le prix corrige doit etre strictement positif.")
        return prix.quantize(Decimal("0.01"))


class CorrectionDistributionService:
    """Correction administrative d'une distribution deja enregistree (sprint-13) :
    superviseur, agent destinataire, produit/lot distribue, quantite et/ou date.

    Toutes les corrections partent des valeurs ORIGINALES (avant toute
    modification) pour resoudre l'AffectationLotSuperviseur source — meme
    limite que AffectationLotService._charger_distribution_directe (pas de FK
    explicite, matching par lot+superviseur+agent). Quand cette source existe,
    elle est maintenue en miroir de la distribution (lot, superviseur, agent,
    quantite_initiale) a chaque correction qui la concerne — sinon une
    correction suivante ne la retrouverait plus. Si le produit ou l'agent
    changent alors que cette distribution porte deja des ventes (ou des
    pertes), la correction est refusee : au-dela de ce point, la vente doit
    etre corrigee separement, pas retargetee vers un autre produit/agent.
    """

    @classmethod
    def corriger_distribution(
        cls,
        detail_distribution_id,
        *,
        agent_terrain=_NON_RENSEIGNE,
        superviseur=_NON_RENSEIGNE,
        lot=_NON_RENSEIGNE,
        quantite=_NON_RENSEIGNE,
        date_distribution=_NON_RENSEIGNE,
        motif='',
        utilisateur,
    ):
        motif = motif or ''
        quantite = AffectationLotService._normaliser_quantite(quantite)
        date_distribution = AffectationLotService._normaliser_date(date_distribution)

        with transaction.atomic():
            detail = DetailDistribution.objects.select_for_update().get(
                pk=detail_distribution_id
            )
            distribution = DistributionAgent.objects.select_for_update().get(
                pk=detail.distribution_id
            )

            ancien_lot = detail.lot
            ancien_superviseur = distribution.superviseur
            ancien_agent = distribution.agent_terrain
            ancienne_quantite = detail.quantite

            nouveau_lot = lot if lot is not _NON_RENSEIGNE else ancien_lot
            nouveau_superviseur = (
                superviseur if superviseur is not _NON_RENSEIGNE else ancien_superviseur
            )
            nouvel_agent = agent_terrain if agent_terrain is not _NON_RENSEIGNE else ancien_agent
            nouvelle_quantite = quantite if quantite is not _NON_RENSEIGNE else ancienne_quantite

            if nouvel_agent and nouvel_agent.superviseur_id != nouveau_superviseur.pk:
                raise ValidationError(
                    f"{nouvel_agent.full_name} n'est pas rattache au superviseur "
                    f"{nouveau_superviseur.full_name}."
                )

            lot_change = nouveau_lot.pk != ancien_lot.pk
            agent_change = bool(ancien_agent) != bool(nouvel_agent) or (
                ancien_agent and nouvel_agent and ancien_agent.pk != nouvel_agent.pk
            )
            superviseur_change = nouveau_superviseur.pk != ancien_superviseur.pk
            quantite_change = nouvelle_quantite != ancienne_quantite
            date_change = (
                date_distribution is not _NON_RENSEIGNE
                and date_distribution != distribution.date_distribution.date()
            )

            quantite_vendue = (
                Vente.objects.filter(
                    detail_distribution=detail, est_supprime=False
                ).aggregate(total=Sum('quantite'))['total']
                or Decimal('0.00')
            )
            if (lot_change or agent_change) and (
                quantite_vendue > 0 or detail.pertes.exists()
            ):
                raise ValidationError(
                    "Cette distribution porte deja des ventes ou des pertes "
                    "enregistrees — impossible de changer l'agent ou le "
                    "produit distribue. Seules la quantite et la date "
                    "restent corrigeables."
                )
            if nouvelle_quantite < quantite_vendue:
                raise ValidationError(
                    "La quantite corrigee ne peut pas etre inferieure aux "
                    f"ventes deja enregistrees ({quantite_vendue})."
                )

            corrections_a_logger = []  # (type_correction, anciennes, nouvelles)
            stock_a_recalculer = lot_change or quantite_change
            affectation = None
            if stock_a_recalculer or agent_change or superviseur_change:
                affectation = cls._trouver_affectation_source(detail, distribution)

            if stock_a_recalculer and affectation is None:
                raise ValidationError(
                    "Impossible d'identifier sans ambiguite le stock source de "
                    "cette distribution — correction de produit/quantite refusee."
                )

            if stock_a_recalculer:
                if not lot_change:
                    lot_obj = LotEntrepot.objects.select_for_update().get(pk=ancien_lot.pk)
                    delta = nouvelle_quantite - ancienne_quantite
                    quantite_restante = lot_obj.quantite_restante - delta
                    if quantite_restante < Decimal('0.00'):
                        raise ValidationError(
                            f"Stock central insuffisant ({lot_obj.quantite_restante} disponible)."
                        )
                    if quantite_restante > lot_obj.quantite_initiale:
                        raise ValidationError(
                            "La correction restituerait plus de stock que la "
                            "quantite initiale du lot."
                        )
                    lot_obj.quantite_restante = quantite_restante
                    lot_obj.save(update_fields=['quantite_restante'])
                else:
                    # Changement de produit : on restitue integralement
                    # l'ancien lot puis on consomme le nouveau — un swap de
                    # stock entre deux lots, pas un simple delta.
                    ancien_lot_obj = LotEntrepot.objects.select_for_update().get(pk=ancien_lot.pk)
                    nouveau_lot_obj = LotEntrepot.objects.select_for_update().get(pk=nouveau_lot.pk)

                    ancien_lot_obj.quantite_restante = (
                        ancien_lot_obj.quantite_restante + ancienne_quantite
                    )
                    ancien_lot_obj.save(update_fields=['quantite_restante'])

                    if nouveau_lot_obj.quantite_restante < nouvelle_quantite:
                        raise ValidationError(
                            f"Stock central insuffisant sur {nouveau_lot_obj.produit.nom} "
                            f"({nouveau_lot_obj.quantite_restante} disponible)."
                        )
                    nouveau_lot_obj.quantite_restante = (
                        nouveau_lot_obj.quantite_restante - nouvelle_quantite
                    )
                    nouveau_lot_obj.save(update_fields=['quantite_restante'])

                    corrections_a_logger.append((
                        'DISTRIBUTION_PRODUIT',
                        {'lot_id': ancien_lot.id, 'produit': ancien_lot.produit.nom},
                        {'lot_id': nouveau_lot.id, 'produit': nouveau_lot.produit.nom},
                    ))

                if quantite_change:
                    corrections_a_logger.append((
                        'DISTRIBUTION_QUANTITE',
                        {'quantite': str(ancienne_quantite)},
                        {'quantite': str(nouvelle_quantite)},
                    ))

                detail.lot = nouveau_lot
                detail.quantite = nouvelle_quantite
                detail.save(update_fields=['lot', 'quantite'])

            if agent_change:
                corrections_a_logger.append((
                    'DISTRIBUTION_AGENT',
                    {
                        'agent_terrain_id': ancien_agent.id if ancien_agent else None,
                        'agent_terrain': ancien_agent.full_name if ancien_agent else None,
                    },
                    {
                        'agent_terrain_id': nouvel_agent.id if nouvel_agent else None,
                        'agent_terrain': nouvel_agent.full_name if nouvel_agent else None,
                    },
                ))
                distribution.agent_terrain = nouvel_agent

            if superviseur_change:
                corrections_a_logger.append((
                    'DISTRIBUTION_SUPERVISEUR',
                    {'superviseur_id': ancien_superviseur.id, 'superviseur': ancien_superviseur.full_name},
                    {'superviseur_id': nouveau_superviseur.id, 'superviseur': nouveau_superviseur.full_name},
                ))
                distribution.superviseur = nouveau_superviseur

            if date_change:
                ancienne_date = distribution.date_distribution
                # Seul le jour est corrige — l'heure d'origine est conservee
                # (meme principe que VenteForm : le geste metier porte sur le
                # jour, pas sur l'heure de saisie).
                nouvelle_date = datetime.combine(date_distribution, ancienne_date.time())
                if timezone.is_naive(nouvelle_date):
                    nouvelle_date = timezone.make_aware(nouvelle_date)
                distribution.date_distribution = nouvelle_date
                corrections_a_logger.append((
                    'DISTRIBUTION_DATE',
                    {'date_distribution': ancienne_date.date().isoformat()},
                    {'date_distribution': date_distribution.isoformat()},
                ))

            if agent_change or superviseur_change or date_change:
                distribution.save()

            if affectation is not None and (agent_change or superviseur_change or stock_a_recalculer):
                affectation.lot = nouveau_lot
                affectation.superviseur = nouveau_superviseur
                affectation.agent_terrain_direct = nouvel_agent
                affectation.quantite_initiale = nouvelle_quantite
                affectation.save(update_fields=[
                    'lot', 'superviseur', 'agent_terrain_direct', 'quantite_initiale'
                ])

            if stock_a_recalculer:
                distribution.quantite_totale = (
                    DetailDistribution.objects.filter(distribution=distribution)
                    .aggregate(total=Sum('quantite'))['total']
                    or Decimal('0.00')
                )
                distribution.save(update_fields=['quantite_totale'])

            for type_correction, anciennes_valeurs, nouvelles_valeurs in corrections_a_logger:
                enregistrer_correction(
                    cible=detail,
                    type_correction=type_correction,
                    motif=motif,
                    utilisateur=utilisateur,
                    anciennes_valeurs=anciennes_valeurs,
                    nouvelles_valeurs=nouvelles_valeurs,
                )

        return detail

    @staticmethod
    def _trouver_affectation_source(detail, distribution):
        candidats = list(
            AffectationLotSuperviseur.objects.select_for_update().filter(
                lot_id=detail.lot_id,
                superviseur_id=distribution.superviseur_id,
                agent_terrain_direct_id=distribution.agent_terrain_id,
            )
        )
        return candidats[0] if len(candidats) == 1 else None


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
