from django import forms
from decimal import Decimal
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError

from core.models import (
    Agent, AffectationLotSuperviseur, DistributionAgent, DetailDistribution, Vente,
)

TYPES_AGENT_TERRAIN = ['terrain', 'agent_gros', 'agent_polivalent', 'stagiaire']


def _queryset_agents_et_soi_meme(superviseur):
    """Agents gérés par ce superviseur + lui-même (pour l'auto-distribution / vente personnelle)."""
    return Agent.objects.filter(
        Q(superviseur=superviseur, type_agent__in=TYPES_AGENT_TERRAIN) | Q(pk=superviseur.pk),
        est_actif=True
    ).select_related('user')


class DistributionForm(forms.Form):
    """
    Flux d'exception uniquement : redistribution d'un stock que le superviseur
    détient encore (Jean ne l'a pas envoyé directement à un agent), ou
    auto-distribution pour une vente personnelle.
    """

    agent_terrain = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Agent destinataire",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    affectation = forms.ModelChoiceField(
        queryset=AffectationLotSuperviseur.objects.none(),
        label="Lot en attente",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    quantite = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Quantité",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)
        self.superviseur = superviseur

        self.fields['agent_terrain'].queryset = _queryset_agents_et_soi_meme(superviseur)
        self.fields['agent_terrain'].label_from_instance = lambda obj: (
            "Moi-même (vente personnelle)" if obj.pk == superviseur.pk else obj.full_name
        )

        self.fields['affectation'].queryset = (
            AffectationLotSuperviseur.objects
            .filter(superviseur=superviseur, agent_terrain_direct__isnull=True, quantite_restante__gt=0)
            .select_related('lot__produit', 'lot__fournisseur')
            .order_by('-date_affectation')
        )
        self.fields['affectation'].label_from_instance = lambda obj: (
            f"{obj.lot.produit.nom} | Reçu {obj.date_affectation:%d/%m/%Y} | Restant : {obj.quantite_restante}"
        )

    def clean(self):
        cleaned_data = super().clean()
        affectation = cleaned_data.get('affectation')
        quantite = cleaned_data.get('quantite')

        if affectation and quantite and quantite > affectation.quantite_restante:
            self.add_error(
                'quantite',
                f"Quantité demandée dépasse le stock disponible ({affectation.quantite_restante})"
            )

        return cleaned_data

    def save(self, superviseur):
        affectation = self.cleaned_data['affectation']
        agent_terrain = self.cleaned_data['agent_terrain']
        quantite = self.cleaned_data['quantite']

        if quantite > affectation.quantite_restante:
            raise ValidationError(f"Stock insuffisant. Disponible : {affectation.quantite_restante}")

        with transaction.atomic():
            distribution = DistributionAgent.objects.create(
                superviseur=superviseur,
                agent_terrain=agent_terrain,
                date_distribution=timezone.now(),
                quantite_totale=quantite,
                nombre_produits_differents=1
            )
            DetailDistribution.objects.create(
                distribution=distribution,
                lot=affectation.lot,
                quantite=quantite,
                prix_gros=None,
                prix_detail=None
            )
            affectation.quantite_restante -= quantite
            affectation.save(update_fields=['quantite_restante'])

        return distribution


class VenteForm(forms.Form):
    """
    Seul point de saisie du prix et du type de vente désormais — plus rien
    n'est hérité d'une distribution pré-remplie (cf. décision marchandise :
    aucun prix n'est fixé avant la vente réelle sur le terrain).

    Toutes les ventes sont enregistrées au comptant (pas de crédit/dette pour
    l'instant) et le type de vente le plus fréquent (détail) est pré-coché.
    La date ne demande que le jour : l'heure exacte est source de blocages
    sur téléphone (fuseau/format de l'input datetime-local) et n'apporte pas
    de valeur métier ici — le système la complète avec l'heure courante.
    """

    agent_terrain = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Agent",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    detail_distribution = forms.ModelChoiceField(
        queryset=DetailDistribution.objects.none(),
        label="Produit distribué",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    quantite = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Quantité vendue",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    type_vente = forms.ChoiceField(
        choices=Vente.TYPE_VENTE_CHOICES,
        label="Type de vente",
        initial='detail',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    prix_vente_unitaire = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Prix unitaire",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'FCFA'})
    )

    date_vente = forms.DateField(
        label="Date de la vente",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)
        self.superviseur = superviseur

        self.fields['agent_terrain'].queryset = _queryset_agents_et_soi_meme(superviseur)
        self.fields['agent_terrain'].label_from_instance = lambda obj: (
            "Moi-même (vente personnelle)" if obj.pk == superviseur.pk else obj.full_name
        )

        # En POST : peupler les distributions actives de l'agent soumis par AJAX
        if 'agent_terrain' in self.data:
            try:
                agent_id = int(self.data.get('agent_terrain'))
                candidats = (
                    DetailDistribution.objects
                    .filter(distribution__superviseur=superviseur, distribution__agent_terrain_id=agent_id)
                    .select_related('lot__produit')
                )
                actifs_ids = [d.pk for d in candidats if d.quantite_restante_calculee > 0]
                self.fields['detail_distribution'].queryset = DetailDistribution.objects.filter(pk__in=actifs_ids)
            except (ValueError, TypeError):
                pass

        self.fields['detail_distribution'].label_from_instance = lambda obj: (
            f"{obj.lot.produit.nom} | reste {obj.quantite_restante_calculee}"
        )

    def clean(self):
        cleaned_data = super().clean()
        agent_terrain = cleaned_data.get('agent_terrain')
        detail_distribution = cleaned_data.get('detail_distribution')
        quantite = cleaned_data.get('quantite')

        if detail_distribution and agent_terrain and detail_distribution.distribution.agent_terrain_id != agent_terrain.id:
            self.add_error(
                'detail_distribution',
                "Cette distribution n'appartient pas à l'agent sélectionné."
            )

        if detail_distribution and quantite and quantite > detail_distribution.quantite_restante_calculee:
            self.add_error(
                'quantite',
                f"Quantité vendue dépasse ce qu'il reste à distribuer ({detail_distribution.quantite_restante_calculee})"
            )

        return cleaned_data

    def save(self):
        # Le système complète l'heure — évite les blocages liés à la saisie
        # d'un datetime complet sur téléphone (fuseau, format navigateur…).
        jour = self.cleaned_data.get('date_vente') or timezone.localdate()
        date_vente = timezone.make_aware(datetime.combine(jour, timezone.localtime().time()))

        return Vente.objects.create(
            agent=self.cleaned_data['agent_terrain'],
            detail_distribution=self.cleaned_data['detail_distribution'],
            quantite=self.cleaned_data['quantite'],
            type_vente=self.cleaned_data['type_vente'],
            prix_vente_unitaire=self.cleaned_data['prix_vente_unitaire'],
            mode_paiement='comptant',
            date_vente=date_vente,
        )
