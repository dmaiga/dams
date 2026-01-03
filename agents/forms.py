from django import forms
from datetime import datetime
from django.utils import timezone
from core.models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,Dette,PaiementDette,
    DistributionAgent, Agent, DetailDistribution, FactureLotEntrepot,BonusAgent,
    MouvementStock,Recouvrement,VersementBancaire,Fournisseur,
    Depense,Perte,RecuVersement,PaiementFournisseur
)

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
