"""Services metier de l'application vente."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from core.models import DetailDistribution, Recouvrement, Vente
from core.services.corrections import enregistrer_correction


_NON_RENSEIGNE = object()


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
        motif,
        utilisateur,
    ):
        if not motif or not motif.strip():
            raise ValidationError("Un motif est obligatoire pour toute correction.")

        prix_vente_unitaire = cls._normaliser_montant(prix_vente_unitaire, "Le prix corrigé")
        quantite = cls._normaliser_montant(quantite, "La quantité corrigée")

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

            if not anciennes_valeurs:
                return vente

            vente.save(update_fields=['quantite', 'prix_vente_unitaire'])

            recouvrement = Recouvrement.objects.select_for_update().filter(vente=vente).first()
            if recouvrement is not None:
                recouvrement.montant_recouvre = vente.total_vente
                recouvrement.save(update_fields=['montant_recouvre'])

            enregistrer_correction(
                cible=vente,
                type_correction='VENTE_PRIX_QUANTITE',
                motif=motif,
                utilisateur=utilisateur,
                anciennes_valeurs=anciennes_valeurs,
                nouvelles_valeurs=nouvelles_valeurs,
            )

        return vente

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
