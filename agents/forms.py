from django import forms
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import models
import os
from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
)

from datetime import timedelta
from django.db.models.functions import Coalesce
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm
from decimal import Decimal  
from django.forms.widgets import FileInput
from django.core.files.uploadedfile import UploadedFile
from agents.services.superviseur_stock_service import SuperviseurStockService


from core.models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,
    Dette,PaiementDette,DistributionAgent, Agent,
    DetailDistribution, FactureLotEntrepot,BonusAgent,
    MouvementStock,Recouvrement,VersementBancaire,Fournisseur,
    Depense,Perte,RecuVersement,PaiementFournisseur,
    AffectationLotSuperviseur,RecouvrementSuperviseur
)







class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True

class MultiFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultiFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class TelephoneOrUsernameLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Téléphone ou Nom d'utilisateur",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Téléphone ou Nom d’utilisateur'
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )


class DirectionAgentCreationForm(forms.ModelForm):
    nom = forms.CharField(max_length=30)
    prenom = forms.CharField(max_length=30)
    telephone = forms.CharField(max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)

    type_agent = forms.ChoiceField(
        choices=Agent.TYPE_AGENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    superviseur = forms.ModelChoiceField(
        queryset=Agent.objects.filter(type_agent='entrepot'),
        required=False
    )

    class Meta:
        model = Agent
        fields = [
            'telephone',
            'type_agent',
            'superviseur',
            'est_actif',
        ]

    def save(self, commit=True):
        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']
        password = self.cleaned_data['password']
        est_actif = self.cleaned_data.get('est_actif', True)

        username = f"{prenom.lower()}.{nom.lower()}"
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{prenom.lower()}.{nom.lower()}{i}"
            i += 1

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=prenom,
            last_name=nom,
            is_active=est_actif
        )

        agent = super().save(commit=False)
        agent.user = user
        agent.telephone = telephone
        agent.est_actif = est_actif

        if commit:
            agent.save()

        return agent


class RotSupervisorCreationForm(forms.ModelForm):
    nom = forms.CharField(max_length=30, required=True)
    prenom = forms.CharField(max_length=30, required=True)
    telephone = forms.CharField(max_length=50, required=True)

    class Meta:
        model = Agent
        fields = ['telephone']

    def save(self, commit=True):
        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']

        username = f"{prenom.lower()}.{nom.lower()}"
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{prenom.lower()}.{nom.lower()}{i}"
            i += 1

        user = User.objects.create_user(
            username=username,
            password="temp123",
            first_name=prenom,
            last_name=nom,
            is_active=True
        )

        agent = super().save(commit=False)
        agent.user = user
        agent.telephone = telephone
        agent.type_agent = 'entrepot'
        agent.type_contrat = 'prestation'
        agent.est_actif = True

        if commit:
            agent.save()

        return agent


# forms.py
class SupervisorTerrainAgentCreationForm(forms.ModelForm):
    nom = forms.CharField(max_length=30, required=True)
    prenom = forms.CharField(max_length=30, required=True)
    telephone = forms.CharField(max_length=50, required=True)

    class Meta:
        model = Agent
        fields = [
            'telephone',
            'marche_affectation',
            'quartier',
        ]

    def __init__(self, *args, **kwargs):
        self.superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)

    def clean_telephone(self):
        telephone = self.cleaned_data['telephone'].replace(' ', '')
        if Agent.objects.filter(telephone=telephone).exists():
            raise ValidationError("Numéro déjà utilisé.")
        return telephone

    def save(self, commit=True):
        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']

        username = f"{prenom.lower()}.{nom.lower()}"
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{prenom.lower()}.{nom.lower()}{i}"
            i += 1

        user = User.objects.create_user(
            username=username,
            password="temp123",
            first_name=prenom,
            last_name=nom,
            is_active=True
        )

        agent = super().save(commit=False)
        agent.user = user
        agent.telephone = telephone
        agent.type_agent = 'terrain'
        agent.superviseur = self.superviseur
        agent.est_actif = True

        if commit:
            agent.save()

        return agent

class RotAffectationLotSuperviseurForm(forms.ModelForm):

    class Meta:
        model = AffectationLotSuperviseur
        fields = ['lot', 'superviseur', 'quantite_initiale']
        widgets = {
            'lot': forms.Select(attrs={'class': 'form-select'}),
            'superviseur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_initiale': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0.5'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.rot = kwargs.pop('rot', None)
        super().__init__(*args, **kwargs)

        if not self.rot or not self.rot.est_rot:
            raise PermissionError("Formulaire réservé au ROT")

        self.fields['lot'].queryset = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).select_related('produit')

        self.fields['superviseur'].queryset = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        ).select_related('user')

        self.fields['quantite_initiale'].label = "Quantité à affecter"

    def clean_quantite_initiale(self):
        quantite = self.cleaned_data.get('quantite_initiale')
        lot = self.cleaned_data.get('lot')

        if not quantite or quantite <= 0:
            raise ValidationError("La quantité doit être supérieure à 0.")

        if lot and quantite > lot.quantite_restante:
            raise ValidationError(
                f"Quantité demandée ({quantite}) supérieure au stock disponible "
                f"({lot.quantite_restante})."
            )

        return quantite

    def clean(self):
        cleaned = super().clean()
        lot = cleaned.get('lot')
        superviseur = cleaned.get('superviseur')

        

        return cleaned

    def save(self, commit=True):
        affectation = super().save(commit=False)

        affectation.quantite_restante = affectation.quantite_initiale
        affectation.attribue_par = self.rot

        if commit:
            affectation.save()

            lot = affectation.lot
            lot.quantite_restante -= affectation.quantite_initiale
            lot.save(update_fields=['quantite_restante'])

        return affectation



class SupervisorDistributionForm(forms.Form):
    agent_terrain = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Agent terrain",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    lot = forms.ModelChoiceField(
        queryset=AffectationLotSuperviseur.objects.none(),
        label="Lot affecté",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    quantite = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        label="Quantité à distribuer",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    prix_gros = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    prix_detail = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)

        # 🔐 AGENTS TERRAIN STRICTEMENT SOUS CE SUPERVISEUR
        self.fields['agent_terrain'].queryset = Agent.objects.filter(
            type_agent='terrain',
            superviseur=self.superviseur,
            est_actif=True
        ).select_related('user')

        # 🔐 LOTS STRICTEMENT AFFECTÉS À CE SUPERVISEUR
        self.fields['lot'].queryset = AffectationLotSuperviseur.objects.filter(
            superviseur=self.superviseur,
            quantite_restante__gt=0
        ).select_related('lot__produit')

    def clean(self):
        cleaned_data = super().clean()
        affectation = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite')

        if affectation and quantite:
            if quantite > affectation.quantite_restante:
                raise ValidationError(
                    f"Stock insuffisant pour ce lot "
                    f"(reste {affectation.quantite_restante})"
                )

        return cleaned_data
  


    def save(self):
        affectation = self.cleaned_data['lot']
        agent_terrain = self.cleaned_data['agent_terrain']
        quantite = self.cleaned_data['quantite']

        # ✅ Distribution
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=agent_terrain
        )

        # ✅ Détail distribution
        DetailDistribution.objects.create(
            distribution=distribution,
            lot=affectation.lot,
            quantite=quantite,
            prix_gros=self.cleaned_data.get('prix_gros'),
            prix_detail=self.cleaned_data.get('prix_detail')
        )

        # ✅ Mise à jour stock affecté
        if quantite > affectation.quantite_restante:
            raise ValidationError("Stock insuffisant")

        affectation.quantite_restante -= quantite
        affectation.save(update_fields=['quantite_restante'])


        # ✅ Synthèse
        distribution.quantite_totale = quantite
        distribution.nombre_produits_differents = 1
        distribution.save(update_fields=[
            'quantite_totale',
            'nombre_produits_differents'
        ])

        return distribution



class RecouvrementSuperviseurForm(forms.ModelForm):

    class Meta:
        model = RecouvrementSuperviseur
        fields = ['superviseur', 'montant',  'commentaire']
        widgets = {
            'superviseur': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control'}),
          
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }

    def __init__(self, *args, **kwargs):
        self.rot = kwargs.pop('rot')
        super().__init__(*args, **kwargs)

        # 🔐 uniquement superviseurs actifs
        self.fields['superviseur'].queryset = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        )

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        superviseur = self.cleaned_data.get('superviseur')
    
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
    
        if superviseur and montant > superviseur.total_recouvre_agents:
            raise forms.ValidationError(
                f"Montant supérieur à l'argent détenu par le superviseur "
                f"({superviseur.total_recouvre_agents} FCFA)."
            )
    
        return montant
    

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.rot = self.rot

        if commit:
            instance.save()

        return instance
