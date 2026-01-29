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
    type_agent = forms.ChoiceField(
        choices=[
            ('terrain', 'Agent (Vente au Détail)'),
            ('agent_gros', 'Agent (Vente en Gros)'),
        ],
        initial='terrain',
        label="Type d'agent"
    )
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
        type_agent = self.cleaned_data['type_agent'] 
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
        agent.type_agent = type_agent 
        agent.superviseur = self.superviseur
        agent.est_actif = True

        if commit:
            agent.save()

        return agent


from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from core.models import AffectationLotSuperviseur, LotEntrepot, Agent

#A INCLURE LES PRIX DANS LE MODEL AFFECTATION LOT SUPERVISEUR

class RotAffectationLotSuperviseurForm(forms.ModelForm):
    # -------------------------------------------------
    # QUANTITÉ (UNITÉS)
    # -------------------------------------------------
    quantite_saisie = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Quantité à affecter (unités)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Ex : 50'
        })
    )

    # -------------------------------------------------
    # PRIX FIXÉS PAR LE ROT
    # -------------------------------------------------
    prix_gros = forms.DecimalField(
        min_value=Decimal('0.00'),
        decimal_places=2,
        label="Prix de gros (unité)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    prix_detail = forms.DecimalField(
        min_value=Decimal('0.00'),
        decimal_places=2,
        label="Prix de détail (unité)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    date_affectation = forms.DateTimeField(
        label="Date et heure de distribution",
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        })
    )
    # =================================================
    # META
    # =================================================
    class Meta:
        model = AffectationLotSuperviseur
        fields = [
            'lot',
            'superviseur',
            'quantite_initiale',
            'prix_gros',
            'prix_detail',
            'date_affectation'
        ]
        widgets = {
            'lot': forms.Select(attrs={'class': 'form-select'}),
            'superviseur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_initiale': forms.HiddenInput(),
        }

    # =================================================
    # INIT
    # =================================================
    def __init__(self, *args, **kwargs):
        self.rot = kwargs.pop('rot', None)
        super().__init__(*args, **kwargs)

        if not self.rot or not self.rot.est_rot:
            raise PermissionError("Formulaire réservé au ROT.")

        self.fields['quantite_initiale'].required = False

        # 🔹 Lots disponibles (stock > 0)
        self.fields['lot'].queryset = (
            LotEntrepot.objects
            .filter(quantite_restante__gt=0)
            .select_related('produit')
            .order_by('produit__nom', 'date_reception')
        )

        # 🔹 Superviseurs actifs
        self.fields['superviseur'].queryset = (
            Agent.objects
            .filter(type_agent='entrepot', est_actif=True)
            .select_related('user')
            .order_by('user__last_name')
        )

    # =================================================
    # CLEAN
    # =================================================
    def clean(self):
        cleaned_data = super().clean()

        lot = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite_saisie')
        prix_gros = cleaned_data.get('prix_gros')
        prix_detail = cleaned_data.get('prix_detail')

        if not lot:
            self.add_error('lot', "Veuillez sélectionner un lot.")
            return cleaned_data

        if not quantite or quantite <= 0:
            self.add_error('quantite_saisie', "Quantité invalide.")
            return cleaned_data

        # --- STOCK ---
        if quantite > lot.quantite_restante:
            self.add_error(
                'quantite_saisie',
                f"Stock insuffisant (disponible : {lot.quantite_restante})."
            )

        # --- PRIX ---
        if prix_gros is None or prix_detail is None:
            raise ValidationError("Les prix doivent être renseignés.")

        if prix_detail < prix_gros:
            raise ValidationError(
                "Le prix de détail doit être supérieur ou égal au prix de gros."
            )

        # --- UNIFICATION ---
        cleaned_data['quantite_initiale'] = quantite

        return cleaned_data

    # =================================================
    # SAVE
    # =================================================
    def save(self, commit=True):
        affectation = super().save(commit=False)

        quantite = self.cleaned_data['quantite_initiale']

        affectation.quantite_initiale = quantite
        affectation.quantite_restante = quantite
        affectation.attribue_par = self.rot

        if commit:
            affectation.save()

            # 🔒 Décrément du stock entrepôt
            lot = affectation.lot
            lot.quantite_restante -= quantite
            lot.save(update_fields=['quantite_restante'])

        return affectation


class SupervisorDistributionForm(forms.Form):

    # -------------------------------------------------
    # AGENT
    # -------------------------------------------------
    agent_terrain = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Agent terrain",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    auto_distribution = forms.BooleanField(
        required=False,
        initial=False,
        label="Auto-distribution",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # -------------------------------------------------
    # LOT AFFECTÉ
    # -------------------------------------------------
    lot = forms.ModelChoiceField(
        queryset=AffectationLotSuperviseur.objects.none(),
        label="Lot affecté",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # -------------------------------------------------
    # QUANTITÉ (UNITÉS)
    # -------------------------------------------------
    quantite = forms.DecimalField(
        min_value=Decimal('0.01'),
        decimal_places=2,
        label="Quantité à distribuer (unités)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )

    # -------------------------------------------------
    # DATE DE DISTRIBUTION
    # -------------------------------------------------
    date_distribution = forms.DateTimeField(
        label="Date et heure de distribution",
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        })
    )

    # =================================================
    # INIT
    # =================================================
    def __init__(self, *args, **kwargs):
        self.superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)

        # Agents terrain rattachés
        self.fields['agent_terrain'].queryset = (
            Agent.objects
            .filter(
                superviseur=self.superviseur,
                type_agent__in=['terrain', 'agent_gros'],
                est_actif=True
            )
            .select_related('user')
            .order_by('user__last_name')
        )

        # Lots affectés encore disponibles
        self.fields['lot'].queryset = (
            AffectationLotSuperviseur.objects
            .filter(
                superviseur=self.superviseur,
                quantite_restante__gt=0
            )
            .select_related('lot__produit')
            .order_by('lot__produit__nom')
        )

    # =================================================
    # CLEAN
    # =================================================
    def clean(self):
        cleaned_data = super().clean()

        auto = cleaned_data.get('auto_distribution')
        agent = cleaned_data.get('agent_terrain')
        affectation = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite')

        # --- AGENT ---
        if auto:
            cleaned_data['agent_terrain'] = self.superviseur
        elif not agent:
            raise ValidationError(
                "Veuillez sélectionner un agent terrain ou activer l’auto-distribution."
            )

        if not affectation or not quantite:
            return cleaned_data

        # --- STOCK ---
        if quantite > affectation.quantite_restante:
            raise ValidationError(
                f"Stock insuffisant (reste {affectation.quantite_restante})."
            )

        return cleaned_data

    # =================================================
    # SAVE
    # =================================================
    def save(self):
        affectation = self.cleaned_data['lot']
        agent = self.cleaned_data['agent_terrain']
        quantite = self.cleaned_data['quantite']
        date_distribution = self.cleaned_data['date_distribution']

        # 1️⃣ Créer la distribution avec date choisie
        distribution = DistributionAgent.objects.create(
            superviseur=self.superviseur,
            agent_terrain=agent,
            date_distribution=date_distribution,
            est_retroactive=date_distribution < timezone.now()
        )

        # 2️⃣ Détail avec PRIX HÉRITÉS (snapshot)
        DetailDistribution.objects.create(
            distribution=distribution,
            lot=affectation.lot,
            quantite=quantite,
            prix_gros=affectation.prix_gros,
            prix_detail=affectation.prix_detail
        )

        # 3️⃣ Décrément du stock superviseur
        affectation.quantite_restante -= quantite
        affectation.save(update_fields=['quantite_restante'])

        # 4️⃣ Stats simples
        distribution.quantite_totale = quantite
        distribution.nombre_produits_differents = 1
        distribution.save(update_fields=[
            'quantite_totale',
            'nombre_produits_differents'
        ])

        return distribution


class RecouvrementSuperviseurForm(forms.ModelForm):

    date_recouvrement = forms.DateTimeField(
        label="Date de remise au ROT",
        initial=timezone.now,
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": "form-control"
            }
        )
    )

    class Meta:
        model = RecouvrementSuperviseur
        fields = [
            'superviseur',
            'montant',
            'date_recouvrement',
            'commentaire',
        ]
        widgets = {
            'superviseur': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Observation éventuelle…'
            }),
        }

    def clean_date_recouvrement(self):
        date = self.cleaned_data['date_recouvrement']

        if date > timezone.now():
            raise ValidationError(
                "La date de recouvrement ne peut pas être dans le futur."
            )

        return date

