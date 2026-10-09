"""Services metier de l'application vente."""

from datetime import date as date_type, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import DetailDistribution, Perte, Recouvrement, Vente
from core.services.corrections import enregistrer_correction
from vente.constants import SEUIL_MARGE_MINIMALE, SEUIL_PRIX_ELEVE


_NON_RENSEIGNE = object()


def details_avec_restant(queryset):
    """Annote chaque DetailDistribution de `restant` (= quantite - ventes non
    supprimees - pertes), en une seule requete SQL.

    Equivalent de `DetailDistribution.quantite_restante_calculee`, qui coute
    2 requetes par detail (N+1 : tres lent pour un agent a l'historique long).
    """
    decimal = DecimalField(max_digits=12, decimal_places=2)
    vendu = (
        Vente.objects.filter(detail_distribution=OuterRef('pk'), est_supprime=False)
        .order_by().values('detail_distribution')
        .annotate(t=Sum('quantite')).values('t')
    )
    perdu = (
        Perte.objects.filter(detail_distribution=OuterRef('pk'))
        .order_by().values('detail_distribution')
        .annotate(t=Sum('quantite_perdue')).values('t')
    )
    return queryset.annotate(
        restant=(
            Coalesce('quantite', 0, output_field=decimal)
            - Coalesce(Subquery(vendu, output_field=decimal), 0, output_field=decimal)
            - Coalesce(Subquery(perdu, output_field=decimal), 0, output_field=decimal)
        )
    )


ANOMALIES_PRIX = (
    ('suspect', "Tous les prix suspects"),
    ('sous_cout', "Vendu sous le prix d'achat"),
    ('marge_faible', "Marge faible"),
    ('prix_eleve', "Prix trop élevé"),
)
# Les libellés n'affichent volontairement AUCUN seuil chiffré : le montant exact ne doit pas
# inciter à enregistrer des ventes juste en dessous.


def q_anomalie_prix(anomalie):
    """Q sur `Vente` pour le filtre d'anomalie de prix (None si valeur inconnue/vide).
    Partagée par la page des correcteurs et la liste des ventes de la direction."""
    achat = F('detail_distribution__lot__prix_achat_unitaire')
    q_sous_cout = Q(prix_vente_unitaire__lt=achat)
    q_marge_faible = Q(prix_vente_unitaire__lt=achat + SEUIL_MARGE_MINIMALE)
    q_prix_eleve = Q(prix_vente_unitaire__gt=achat + SEUIL_PRIX_ELEVE)
    return {
        'sous_cout': q_sous_cout,
        'marge_faible': q_marge_faible,
        'prix_eleve': q_prix_eleve,
        'suspect': q_marge_faible | q_prix_eleve,
    }.get(anomalie)


def classer_prix(prix_vente, prix_achat):
    """Étiquette d'alerte d'une vente (`sous_cout` | `marge_faible` | `prix_eleve`)
    ou None — mêmes règles que le filtre `anomalie`."""
    if prix_vente < prix_achat:
        return 'sous_cout'
    if prix_vente < prix_achat + SEUIL_MARGE_MINIMALE:
        return 'marge_faible'
    if prix_vente > prix_achat + SEUIL_PRIX_ELEVE:
        return 'prix_eleve'
    return None


def lister_ventes_a_surveiller(
    *, agent_id=None, superviseur_id=None, produit_id=None, fournisseur_id=None,
    anomalie=None, debut=None, fin=None,
):
    """Ventes non supprimées, filtrées pour la surveillance des prix saisis
    (page dédiée au groupe « Correcteurs ventes »). Porte tout ce qu'il faut
    pour repérer une erreur sans N+1 : lot (prix d'achat, date de réception),
    fournisseur, superviseur de la distribution et agent vendeur.

    `anomalie` (voir `ANOMALIES_PRIX`) : `sous_cout` (prix < achat — confusion prix
    au kilo / prix au sac), `marge_faible` (prix < achat + SEUIL_MARGE_MINIMALE, sous-coût
    inclus), `prix_eleve` (prix > achat + SEUIL_PRIX_ELEVE, probable faute de frappe) ou
    `suspect` (marge faible OU prix élevé).
    """
    ventes = Vente.objects.filter(est_supprime=False).select_related(
        'agent__user',
        'detail_distribution__lot__produit',
        'detail_distribution__lot__fournisseur',
        'detail_distribution__distribution__superviseur__user',
    )
    if agent_id:
        ventes = ventes.filter(agent_id=agent_id)
    if superviseur_id:
        ventes = ventes.filter(detail_distribution__distribution__superviseur_id=superviseur_id)
    if produit_id:
        ventes = ventes.filter(detail_distribution__lot__produit_id=produit_id)
    if fournisseur_id:
        ventes = ventes.filter(detail_distribution__lot__fournisseur_id=fournisseur_id)
    q_anomalie = q_anomalie_prix(anomalie)
    if q_anomalie is not None:
        ventes = ventes.filter(q_anomalie)
    if debut:
        ventes = ventes.filter(date_vente__date__gte=debut)
    if fin:
        ventes = ventes.filter(date_vente__date__lte=fin)
    return ventes.order_by('-date_vente')


class CorrectionVenteService:
    """Correction administrative du prix et/ou de la quantite d'une Vente
    deja enregistree (sprint-13).

    Cas d'usage recurrent releve par la direction : confusion entre prix au
    sac (produit conditionne) et prix au kilo (produit vrac) saisi par le
    superviseur, ou erreur de quantite. Aucune garde liee a un recouvrement
    deja remis au ROT/direction : le recouvrement/versement reel est suivi
    hors systeme (agent dedie + groupe WhatsApp) — voir docs/sprints/
    sprint-13.md et la memoire projet associee.
    """

    @classmethod
    def corriger_vente(
        cls,
        vente_id,
        *,
        prix_vente_unitaire=_NON_RENSEIGNE,
        quantite=_NON_RENSEIGNE,
        date_vente=_NON_RENSEIGNE,
        motif='',
        utilisateur,
    ):
        motif = motif or ''

        prix_vente_unitaire = cls._normaliser_montant(prix_vente_unitaire, "Le prix corrigé")
        quantite = cls._normaliser_montant(quantite, "La quantité corrigée")
        date_vente = cls._normaliser_date(date_vente)

        with transaction.atomic():
            vente = Vente.objects.select_for_update().get(pk=vente_id, est_supprime=False)
            detail = DetailDistribution.objects.select_for_update().get(
                pk=vente.detail_distribution_id
            )

            if hasattr(vente, 'dette'):
                raise ValidationError(
                    "Cette vente porte une dette associée — correction non gérée pour "
                    "l'instant (aucune vente à crédit en usage actuellement)."
                )

            anciennes_valeurs = {}
            nouvelles_valeurs = {}
            corrections_a_logger = []  # (type_correction, anciennes, nouvelles)
            ancienne_quantite = vente.quantite
            ancien_prix = vente.prix_vente_unitaire

            if quantite is not _NON_RENSEIGNE and quantite != vente.quantite:
                autres_ventes = (
                    Vente.objects.filter(detail_distribution=detail, est_supprime=False)
                    .exclude(pk=vente.pk)
                    .aggregate(total=Sum('quantite'))['total']
                    or Decimal('0.00')
                )
                quantite_perdue = (
                    detail.pertes.aggregate(total=Sum('quantite_perdue'))['total']
                    or Decimal('0.00')
                )
                if autres_ventes + quantite_perdue + quantite > detail.quantite:
                    disponible = detail.quantite - autres_ventes - quantite_perdue
                    raise ValidationError(
                        "Quantité corrigée supérieure au disponible sur cette "
                        f"distribution ({disponible})."
                    )
                delta = quantite - vente.quantite
                detail.quantite_vendue = detail.quantite_vendue + delta
                detail.save(update_fields=['quantite_vendue'])

                vente.quantite = quantite
                anciennes_valeurs['quantite'] = str(ancienne_quantite)
                nouvelles_valeurs['quantite'] = str(quantite)

            if (
                prix_vente_unitaire is not _NON_RENSEIGNE
                and prix_vente_unitaire != vente.prix_vente_unitaire
            ):
                vente.prix_vente_unitaire = prix_vente_unitaire
                anciennes_valeurs['prix_vente_unitaire'] = str(ancien_prix)
                nouvelles_valeurs['prix_vente_unitaire'] = str(prix_vente_unitaire)

            if anciennes_valeurs:
                corrections_a_logger.append(('VENTE_PRIX_QUANTITE', anciennes_valeurs, nouvelles_valeurs))

            if date_vente is not _NON_RENSEIGNE and date_vente != vente.date_vente.date():
                ancienne_date = vente.date_vente
                # Seul le jour est corrige — l'heure d'origine est conservee
                # (meme principe que VenteForm.save() a la creation).
                nouvelle_date = datetime.combine(date_vente, ancienne_date.time())
                if timezone.is_naive(nouvelle_date):
                    nouvelle_date = timezone.make_aware(nouvelle_date)
                vente.date_vente = nouvelle_date
                corrections_a_logger.append((
                    'VENTE_DATE',
                    {'date_vente': ancienne_date.date().isoformat()},
                    {'date_vente': date_vente.isoformat()},
                ))

            if not corrections_a_logger:
                return vente

            vente.save(update_fields=['quantite', 'prix_vente_unitaire', 'date_vente'])

            if anciennes_valeurs:
                recouvrement = Recouvrement.objects.select_for_update().filter(vente=vente).first()
                if recouvrement is not None:
                    recouvrement.montant_recouvre = vente.total_vente
                    recouvrement.save(update_fields=['montant_recouvre'])

            for type_correction, anciennes, nouvelles in corrections_a_logger:
                enregistrer_correction(
                    cible=vente,
                    type_correction=type_correction,
                    motif=motif,
                    utilisateur=utilisateur,
                    anciennes_valeurs=anciennes,
                    nouvelles_valeurs=nouvelles,
                )

        return vente

    @staticmethod
    def _normaliser_date(valeur):
        if valeur is _NON_RENSEIGNE:
            return valeur
        if isinstance(valeur, datetime):
            return valeur.date()
        if not isinstance(valeur, date_type):
            raise ValidationError("La date de vente corrigée est invalide.")
        return valeur

    @staticmethod
    def _normaliser_montant(valeur, libelle):
        if valeur is _NON_RENSEIGNE:
            return valeur
        try:
            montant = Decimal(str(valeur))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError(f"{libelle} doit être un nombre décimal valide.") from exc
        if not montant.is_finite() or montant <= Decimal("0.00"):
            raise ValidationError(f"{libelle} doit être strictement positif.")
        return montant.quantize(Decimal("0.01"))
