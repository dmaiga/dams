from django import forms
from decimal import Decimal

from django.utils import timezone
from django.core.exceptions import ValidationError

from core.models import Produit, LotEntrepot, AffectationLotSuperviseur, Agent


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

    prix_gros = forms.DecimalField(
        min_value=Decimal('0.00'),
        decimal_places=2,
        label="Prix de vente gros",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'FCFA'
        })
    )

    prix_detail = forms.DecimalField(
        min_value=Decimal('0.00'),
        decimal_places=2,
        label="Prix de vente détail",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'FCFA'
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

        self.fields['lot'].label_from_instance = lambda obj: (
            f"{obj.produit.nom} | "
            f"{obj.fournisseur.nom if obj.fournisseur else '—'} | "
            f"{timezone.localtime(obj.date_reception).strftime('%d/%m/%Y')} | "
            f"Disponible : {obj.quantite_restante}"
        )

    def clean(self):
        cleaned_data = super().clean()
        lot = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite')

        if lot and quantite:
            if quantite > lot.quantite_restante:
                self.add_error(
                    'quantite',
                    f"Quantité demandée dépasse le stock disponible ({lot.quantite_restante})"
                )

        return cleaned_data

    def save(self, agent):
        from django.db import transaction

        lot = self.cleaned_data['lot']
        quantite = self.cleaned_data['quantite']

        if quantite > lot.quantite_restante:
            raise ValidationError(f"Stock insuffisant. Disponible : {lot.quantite_restante}")

        with transaction.atomic():
            affectation = AffectationLotSuperviseur.objects.create(
                lot=lot,
                superviseur=self.cleaned_data['superviseur'],
                quantite_initiale=quantite,
                quantite_restante=quantite,
                prix_gros=self.cleaned_data['prix_gros'],
                prix_detail=self.cleaned_data['prix_detail'],
                date_affectation=(
                    self.cleaned_data.get('date_affectation') or timezone.now().date()
                ),
                attribue_par=agent
            )

            lot.quantite_restante -= quantite
            lot.quantite_disponible_rot += quantite
            lot.save(update_fields=['quantite_restante', 'quantite_disponible_rot'])

        return affectation
