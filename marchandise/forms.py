from django import forms
from decimal import Decimal

from django.utils import timezone
from django.core.exceptions import ValidationError

from core.models import (
    Produit, LotEntrepot, AffectationLotSuperviseur, Agent,
    DistributionAgent, DetailDistribution,
)

TYPES_AGENT_TERRAIN = ['terrain', 'agent_gros', 'agent_polivalent', 'stagiaire']


class AffectationSuperviseurForm(forms.Form):

    produit = forms.ModelChoiceField(
        queryset=Produit.objects.all().order_by('nom'),
        label="Produit",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    lot = forms.ModelChoiceField(
        queryset=LotEntrepot.objects.none(),
        label="Lot",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    superviseur = forms.ModelChoiceField(
        queryset=Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        ).select_related('user').order_by('user__last_name'),
        label="Superviseur destinataire",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    agent_terrain = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Distribution directe à un agent",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=(
            "Optionnel — si renseigné, la marchandise part directement à cet agent "
            "sous la supervision du superviseur choisi, sans étape intermédiaire."
        )
    )

    quantite = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Quantité à affecter",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Ex : 50'
        })
    )

    date_affectation = forms.DateField(
        label="Date de sortie",
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # En POST : valider le lot soumis par AJAX
        if 'lot' in self.data:
            try:
                lot_id = int(self.data.get('lot'))
                self.fields['lot'].queryset = LotEntrepot.objects.filter(
                    pk=lot_id,
                    quantite_restante__gt=0
                ).select_related('fournisseur')
            except (ValueError, TypeError):
                pass

        self.fields['superviseur'].label_from_instance = lambda obj: obj.full_name

        self.fields['lot'].label_from_instance = lambda obj: (
            f"{obj.produit.nom} | "
            f"{obj.fournisseur.nom if obj.fournisseur else '—'} | "
            f"{timezone.localtime(obj.date_reception).strftime('%d/%m/%Y')} | "
            f"Disponible : {obj.quantite_restante}"
        )

        # En POST : peupler les agents rattachés au superviseur soumis par AJAX
        if 'superviseur' in self.data:
            try:
                superviseur_id = int(self.data.get('superviseur'))
                self.fields['agent_terrain'].queryset = Agent.objects.filter(
                    superviseur_id=superviseur_id,
                    type_agent__in=TYPES_AGENT_TERRAIN,
                    est_actif=True
                ).select_related('user')
            except (ValueError, TypeError):
                pass

        self.fields['agent_terrain'].label_from_instance = lambda obj: obj.full_name

    def clean(self):
        cleaned_data = super().clean()
        lot = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite')
        superviseur = cleaned_data.get('superviseur')
        agent_terrain = cleaned_data.get('agent_terrain')

        if lot and quantite:
            if quantite > lot.quantite_restante:
                self.add_error(
                    'quantite',
                    f"Quantité demandée dépasse le stock disponible ({lot.quantite_restante})"
                )

        if agent_terrain and superviseur and agent_terrain.superviseur_id != superviseur.id:
            self.add_error(
                'agent_terrain',
                "Cet agent n'est pas rattaché au superviseur sélectionné."
            )

        return cleaned_data

    def save(self, agent):
        from django.db import transaction

        lot = self.cleaned_data['lot']
        quantite = self.cleaned_data['quantite']
        superviseur = self.cleaned_data['superviseur']
        agent_terrain = self.cleaned_data.get('agent_terrain')

        if quantite > lot.quantite_restante:
            raise ValidationError(f"Stock insuffisant. Disponible : {lot.quantite_restante}")

        with transaction.atomic():
            affectation = AffectationLotSuperviseur.objects.create(
                lot=lot,
                superviseur=superviseur,
                quantite_initiale=quantite,
                quantite_restante=quantite,
                date_affectation=(
                    self.cleaned_data.get('date_affectation') or timezone.now().date()
                ),
                attribue_par=agent
            )

            lot.quantite_restante -= quantite
            lot.quantite_disponible_rot += quantite
            lot.save(update_fields=['quantite_restante', 'quantite_disponible_rot'])

            if agent_terrain:
                distribution = DistributionAgent.objects.create(
                    superviseur=superviseur,
                    agent_terrain=agent_terrain,
                    date_distribution=timezone.now(),
                    quantite_totale=quantite,
                    nombre_produits_differents=1
                )
                DetailDistribution.objects.create(
                    distribution=distribution,
                    lot=lot,
                    quantite=quantite,
                    prix_gros=affectation.prix_gros,
                    prix_detail=affectation.prix_detail
                )
                # Tout est parti directement à l'agent : rien ne reste au niveau du superviseur
                affectation.quantite_restante = Decimal('0.00')
                affectation.agent_terrain_direct = agent_terrain
                affectation.save(update_fields=['quantite_restante', 'agent_terrain_direct'])

        return affectation
