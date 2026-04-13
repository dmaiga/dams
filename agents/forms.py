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

from django.db import transaction





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
    #  Infos utilisateur
    nom = forms.CharField(max_length=30)
    prenom = forms.CharField(max_length=30)
    telephone = forms.CharField(max_length=50)

    #  Affectation
    quartier = forms.CharField(max_length=150, required=False)
    marche_affectation = forms.CharField(max_length=150, required=False)

    #  RH
    date_debut_fonction = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    salaire_base_personnel = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2
    )

    type_contrat = forms.ChoiceField(
        choices=Agent.TYPE_CONTRAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_fin_contrat = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    #  Organisation
    type_agent = forms.ChoiceField(
        choices=Agent.TYPE_AGENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    superviseur = forms.ModelChoiceField(
        queryset=Agent.objects.filter(type_agent='entrepot',est_actif=True),
        required=False
    )

    class Meta:
        model = Agent
        fields = [
            'telephone',
            'type_agent',
            'superviseur',
            'est_actif',
            'quartier',
            'marche_affectation',
            'date_debut_fonction',
            'salaire_base_personnel',
            'type_contrat',
            'date_fin_contrat',
        ]

    def save(self, commit=True):
        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']
        est_actif = self.cleaned_data.get('est_actif', True)
    
        # RH
        quartier = self.cleaned_data.get('quartier')
        marche = self.cleaned_data.get('marche_affectation')
        date_debut = self.cleaned_data.get('date_debut_fonction')
        salaire = self.cleaned_data.get('salaire_base_personnel')
        type_contrat = self.cleaned_data.get('type_contrat')
        date_fin = self.cleaned_data.get('date_fin_contrat')
    
        #  password générique
        password = "temp123"
    
        # username auto
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
    
        #  Champs ajoutés
        agent.quartier = quartier
        agent.marche_affectation = marche
        agent.date_debut_fonction = date_debut
        agent.salaire_base_personnel = salaire
        agent.type_contrat = type_contrat
        agent.date_fin_contrat = date_fin
    
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

    date_debut_fonction = forms.DateField(
        required=True,
        label="Date de prise de fonction",
        widget=forms.DateInput(attrs={'type': 'date'})
    )

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
            'date_debut_fonction',
        ]

    def __init__(self, *args, **kwargs):
        self.superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)

    # -------------------------
    # VALIDATIONS
    # -------------------------

    def clean_telephone(self):
        telephone = self.cleaned_data['telephone']
        telephone = telephone.replace(' ', '').strip()

        if Agent.objects.filter(
            telephone=telephone,
            est_actif=True
        ).exists():
            raise ValidationError("Numéro déjà utilisé.")

        return telephone

    def clean_date_debut_fonction(self):
        date_debut = self.cleaned_data['date_debut_fonction']

        if date_debut > timezone.now().date():
            raise ValidationError("La date ne peut pas être dans le futur.")

        return date_debut

    # -------------------------
    # SAVE ATOMIQUE
    # -------------------------

    @transaction.atomic
    def save(self, commit=True):

        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']
        type_agent = self.cleaned_data['type_agent']
        date_debut = self.cleaned_data['date_debut_fonction']

        # username unique
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
        agent.date_debut_fonction = date_debut

        if not agent.salaire_base_personnel:
            agent.salaire_base_personnel = Decimal("20000")

        if commit:
            agent.save()

        return agent


class SupervisorTerrainAgentUpdateForm(forms.ModelForm):

    date_debut_fonction = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Agent
        fields = [
            'telephone',
            'marche_affectation',
            'quartier',
            'date_debut_fonction',
            'est_actif',
        ]

    def clean_telephone(self):
        telephone = self.cleaned_data['telephone']
        telephone = telephone.replace(' ', '').strip()

        qs = Agent.objects.filter(
            telephone=telephone,
            est_actif=True
        ).exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Numéro déjà utilisé.")

        return telephone

    def clean_date_debut_fonction(self):
        date_debut = self.cleaned_data['date_debut_fonction']

        if date_debut > timezone.now().date():
            raise ValidationError("La date ne peut pas être future.")

        return date_debut

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
        label="Date de distribution",
        widget=forms.DateInput(attrs={  
            'type': 'date',
            'class': 'form-control'
        }),
        input_formats=['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'],
        required=False
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
            .order_by('-date_affectation')
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


class VenteSuperviseurSimplifieeForm(forms.Form):

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        label="Agent"
    )

    affectation = forms.ModelChoiceField(
        queryset=AffectationLotSuperviseur.objects.none(),
        label="Produit (stock disponible)"
    )

    quantite = forms.DecimalField(
        
        label="Quantité"
    )

    def __init__(self, *args, **kwargs):
        superviseur = kwargs.pop('superviseur')
        super().__init__(*args, **kwargs)

        # =========================
        # AGENTS DU SUPERVISEUR
        # =========================
        self.fields['agent'].queryset = Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=['terrain', 'agent_gros'],
            est_actif=True
        ).select_related('user')

        # =========================
        # STOCK DISPONIBLE
        # =========================
        qs = (
            AffectationLotSuperviseur.objects
            .filter(
                superviseur=superviseur,
                quantite_restante__gt=0
            )
            .select_related('lot__produit')
            .order_by('-date_affectation')
        )

        self.fields['affectation'].queryset = qs

        # =========================
        # AFFICHAGE LISIBLE
        # =========================
        self.fields['affectation'].label_from_instance = lambda obj: (
            f"{obj.lot.produit.nom} | "
            f"{obj.lot.date_reception.strftime('%d/%m/%Y')} | "
            f"I/R: {obj.quantite_initiale}/{obj.quantite_restante} | "
            
            f"Affecté le: {obj.date_affectation.strftime('%d/%m/%Y')}"
            
        )

        # =========================
        # UI Bootstrap
        # =========================
        self.fields['agent'].widget.attrs.update({'class': 'form-select'})
        self.fields['affectation'].widget.attrs.update({'class': 'form-select'})
        self.fields['quantite'].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        affectation = cleaned_data.get('affectation')
        quantite = cleaned_data.get('quantite')
    
        if affectation and quantite:
            if quantite > affectation.quantite_restante:
                raise forms.ValidationError(
                    "Quantité supérieure au stock disponible"
                )
    
        return cleaned_data
