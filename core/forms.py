from django import forms
from datetime import datetime
from django.utils import timezone
from .models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,Dette,PaiementDette,
    DistributionAgent, Agent, DetailDistribution, Facture,BonusAgent,
    MouvementStock,Recouvrement,VersementBancaire,Fournisseur,
    Depense,Perte,RecuVersement
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


class AgentCreationForm(forms.ModelForm):
    nom = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'})
    )
    prenom = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'})
    )
    telephone = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone'})
    )
    type_agent = forms.ChoiceField(
        choices=[
            ('stagiaire', 'Stagiaire (Test - 15 jours)'),
            ('terrain', 'Agent Terrain'),
            ('entrepot', 'Superviseur'),  # ✅ Maintenant les superviseurs peuvent créer d'autres superviseurs
        ], 
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='stagiaire'
    )
    # Champ optionnel pour la date de mise en service
    date_mise_service = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        label="Date de mise en service (optionnel)",
        help_text="Laisser vide pour utiliser la date actuelle"
    )

    class Meta:
        model = Agent
        fields = ['telephone', 'type_agent','date_mise_service']

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        # ✅ Nettoyer le numéro
        telephone = telephone.strip().replace(' ', '').replace('-', '')
        
        if not telephone.isdigit():
            raise ValidationError("Le numéro de téléphone ne doit contenir que des chiffres.")
            
        if Agent.objects.filter(telephone=telephone).exists():
            raise ValidationError("Ce numéro de téléphone est déjà utilisé.")
            
        return telephone

    def generate_unique_username(self, nom, prenom):
        """
        Génère un username unique basé sur prenom+nom
        En cas de doublon, ajoute un chiffre incrémental
        """
        base_username = f"{prenom.lower()}.{nom.lower()}"
        username = base_username
        
        # ✅ Nettoyer les caractères spéciaux
        username = username.replace(' ', '').replace('-', '').replace("'", "")
        
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        return username

    def save(self, commit=True):
        nom = self.cleaned_data['nom']
        prenom = self.cleaned_data['prenom']
        telephone = self.cleaned_data['telephone']
        type_agent = self.cleaned_data['type_agent']
        date_mise_service = self.cleaned_data.get('date_mise_service')
        
        # ✅ Générer un username unique
        username = self.generate_unique_username(nom, prenom)
        
        # ✅ Créer l'utilisateur avec mot de passe par défaut
        user = User.objects.create_user(
            username=username,  # ✅ prenom.nom (unique)
            password='temp123',  # ✅ Mot de passe par défaut
            first_name=prenom,   # ✅ CORRECTION: first_name = prénom
            last_name=nom,       # ✅ CORRECTION: last_name = nom
            email=f"{username}@example.com",  # Email optionnel
            is_active=True
        )
        
        # ✅ Créer l'agent
        agent = super().save(commit=False)
        agent.user = user
        agent.telephone = telephone

        # ✅ Si date de mise en service fournie manuellement
        if date_mise_service and type_agent == 'stagiaire':
            agent.date_mise_service = date_mise_service
        if commit:
            agent.save()
            
        return agent

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

# forms.py
class AgentModificationForm(forms.ModelForm):
    nom = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    prenom = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    type_agent = forms.ChoiceField(
        choices=[
            ('stagiaire', 'Stagiaire'),  
            ('terrain', 'Agent Terrain'),
            ('entrepot', 'Superviseur'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Agent
        fields = ['telephone', 'type_agent']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['nom'].initial = self.instance.user.first_name
            self.fields['prenom'].initial = self.instance.user.last_name
        
        # ✅ CORRECTION : Montrer le type RÉEL de l'agent
        if self.instance and self.instance.pk:
            # Si c'est un stagiaire, on garde 'terrain' comme suggestion
            if self.instance.est_stagiaire:
                self.fields['type_agent'].initial = 'terrain'
            else:
                # Pour les autres types, on montre leur type actuel
                self.fields['type_agent'].initial = self.instance.type_agent

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if Agent.objects.filter(telephone=telephone).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return telephone

    def save(self, commit=True):
        if self.instance and self.instance.user:
            self.instance.user.first_name = self.cleaned_data['nom']
            self.instance.user.last_name = self.cleaned_data['prenom']
            self.instance.user.save()
        
        return super().save(commit=commit)

class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ['nom', 'contact', 'email', 'adresse']

class ReceptionLotForm(forms.ModelForm):
    # Champs pour nouveau fournisseur
    nouveau_fournisseur = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Créer un nouveau fournisseur"
    )
    nouveau_fournisseur_nom = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du fournisseur'
        }),
        label="Nom du fournisseur"
    )
    nouveau_fournisseur_contact = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Contact (téléphone, email...)'
        }),
        label="Contact"
    )
    
    # Champs pour nouveau produit
    nouveau_produit = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Créer un nouveau produit"
    )
    nouveau_produit_nom = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du produit'
        }),
        label="Nom du produit"
    )
    nouveau_produit_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'placeholder': 'Description (optionnel)',
            'rows': 2
        }),
        label="Description"
    )
    
    facture = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
        }),
        label="Facture (optionnel)"
    )
    
    class Meta:
        model = LotEntrepot
        fields = ['produit', 'fournisseur', 'quantite_initiale',
                  'prix_achat_unitaire', 'date_reception', 'facture']
        widgets = {
            'produit': forms.Select(attrs={
                'class': 'form-select',
                'data-placeholder': 'Sélectionner un produit...'
            }),
            'fournisseur': forms.Select(attrs={
                'class': 'form-select',
                'data-placeholder': 'Sélectionner un fournisseur...'
            }),
            'quantite_initiale': forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.5',   
            'min': '0.5',
            'placeholder': 'Quantité'
             }),
            'prix_achat_unitaire': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '1',
                'placeholder': '0.00'
            }),
            'date_reception': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
        labels = {
            'quantite_initiale': 'Quantité initiale',
            'prix_achat_unitaire': 'Prix d\'achat unitaire (FCFA)',
            'date_reception': 'Date et heure de réception'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configuration des champs requis
        self.fields['produit'].required = False
        self.fields['fournisseur'].required = False
        self.fields['quantite_initiale'].required = True
        self.fields['prix_achat_unitaire'].required = True
        self.fields['date_reception'].required = True
        self.fields['facture'].required = False
        
        # Peupler les listes déroulantes avec tri alphabétique
        self.fields['produit'].queryset = Produit.objects.all().order_by('nom')
        self.fields['produit'].empty_label = "Sélectionner un produit..."
        self.fields['fournisseur'].queryset = Fournisseur.objects.all().order_by('nom')
        self.fields['fournisseur'].empty_label = "Sélectionner un fournisseur..."
        
        # Définir la date actuelle comme valeur par défaut
        self.fields['date_reception'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        nouveau_fournisseur = cleaned_data.get('nouveau_fournisseur')
        nouveau_produit = cleaned_data.get('nouveau_produit')
        
        # Validation fournisseur
        if nouveau_fournisseur:
            nom_fournisseur = cleaned_data.get('nouveau_fournisseur_nom')
            if not nom_fournisseur or not nom_fournisseur.strip():
                self.add_error('nouveau_fournisseur_nom', 'Le nom du fournisseur est requis')
            elif Fournisseur.objects.filter(nom__iexact=nom_fournisseur.strip()).exists():
                self.add_error('nouveau_fournisseur_nom', 'Ce fournisseur existe déjà')
        else:
            # Si aucun fournisseur sélectionné, on laisse vide (sera remplacé par défaut plus tard)
            if not cleaned_data.get('fournisseur'):
                cleaned_data['fournisseur'] = None

        # Validation produit
        if nouveau_produit:
            nom_produit = cleaned_data.get('nouveau_produit_nom')
            if not nom_produit or not nom_produit.strip():
                self.add_error('nouveau_produit_nom', 'Le nom du produit est requis')
            elif Produit.objects.filter(nom__iexact=nom_produit.strip()).exists():
                self.add_error('nouveau_produit_nom', 'Ce produit existe déjà')
        else:
            if not cleaned_data.get('produit'):
                self.add_error('produit', 'Veuillez sélectionner un produit existant')
        
        # Validation des champs obligatoires
        quantite = cleaned_data.get('quantite_initiale')
        if not quantite or quantite <= 0:
            self.add_error('quantite_initiale', 'La quantité doit être supérieure à 0')
        

        # Validation de la date de réception
        date_reception = cleaned_data.get('date_reception')
        if date_reception:
            if date_reception > timezone.now():
                self.add_error('date_reception', 'La date de réception ne peut pas être dans le futur')
        else:
            self.add_error('date_reception', 'La date de réception est requise')
        
        # Validation de la facture
        facture = cleaned_data.get('facture')
        if facture:
            # Vérifier la taille du fichier (max 10MB)
            if facture.size > 10 * 1024 * 1024:
                self.add_error('facture', 'La facture ne doit pas dépasser 10MB')
            
            # Vérifier l'extension
            extensions_autorisees = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            extension = os.path.splitext(facture.name)[1].lower()
            if extension not in extensions_autorisees:
                self.add_error('facture', 
                    f'Type de fichier non autorisé. Formats acceptés: {", ".join(extensions_autorisees)}')
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
    
        # Gérer le fournisseur
        if self.cleaned_data.get('nouveau_fournisseur'):
            fournisseur_nom = self.cleaned_data['nouveau_fournisseur_nom'].strip()
            fournisseur_contact = self.cleaned_data.get('nouveau_fournisseur_contact', '').strip()
            
            fournisseur, created = Fournisseur.objects.get_or_create(
                nom=fournisseur_nom,
                defaults={'contact': fournisseur_contact}
            )
            instance.fournisseur = fournisseur
        elif not self.cleaned_data.get('fournisseur'):
            # Fournisseur par défaut si rien n’est renseigné
            fournisseur_defaut, _ = Fournisseur.objects.get_or_create(
                nom="Fournisseur Inconnu",
                defaults={'contact': 'N/A', 'adresse': 'Non renseignée'}
            )
            instance.fournisseur = fournisseur_defaut
    
        # Gérer le produit
        if self.cleaned_data.get('nouveau_produit'):
            produit_nom = self.cleaned_data['nouveau_produit_nom'].strip()
            produit_description = self.cleaned_data.get('nouveau_produit_description', '').strip()
            
            produit, created = Produit.objects.get_or_create(
                nom=produit_nom,
                defaults={'description': produit_description}
            )
            instance.produit = produit

        # Générer une référence de lot
        if not instance.reference_lot:
            prefix = timezone.now().strftime("%Y%m%d")
            dernier_lot = LotEntrepot.objects.filter(
                reference_lot__startswith=prefix
            ).order_by('-reference_lot').first()
            
            if dernier_lot:
                try:
                    dernier_num = int(dernier_lot.reference_lot[-4:])
                    nouveau_num = dernier_num + 1
                except (ValueError, IndexError):
                    nouveau_num = 1
            else:
                nouveau_num = 1
                
            instance.reference_lot = f"{prefix}-{nouveau_num:04d}"

        # Initialiser la quantité restante
        instance.quantite_restante = instance.quantite_initiale
        
        # Gérer la facture
        if self.cleaned_data.get('facture'):
            instance.date_upload_facture = timezone.now()

        if commit:
            instance.save()
            # Créer le mouvement de stock après sauvegarde
            MouvementStock.objects.create(
                produit=instance.produit,
                lot=instance,
                type_mouvement='RECEPTION',
                quantite=instance.quantite_initiale,
                date_mouvement=instance.date_reception,

            )
            
        return instance 
    
    # forms.py

# core/forms.py


class PerteForm(forms.ModelForm):
    class Meta:
        model = Perte
        fields = ["quantite_perdue", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class UploadFactureForm(forms.ModelForm):
    class Meta:
        model = LotEntrepot
        fields = ['facture']
        widgets = {
            'facture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            })
        }

    def clean_facture(self):
        facture = self.cleaned_data.get('facture')
        if facture:
            # Vérifier la taille du fichier (max 10MB)
            if facture.size > 10 * 1024 * 1024:
                raise forms.ValidationError('La facture ne doit pas dépasser 10MB')
            
            # Vérifier l'extension
            extensions_autorisees = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            extension = os.path.splitext(facture.name)[1].lower()
            if extension not in extensions_autorisees:
                raise forms.ValidationError(
                    f'Type de fichier non autorisé. Formats acceptés: {", ".join(extensions_autorisees)}'
                )
        return facture
# forms.py

class DistributionForm(forms.ModelForm):
    TYPE_DISTRIBUTION = (
        ('TERRAIN', 'Distribution à un agent'),
        ('AUTO', 'Auto-distribution'),
        ('STAGIAIRE', 'Distribution à un stagiaire'),
    )
    
    type_distribution = forms.ChoiceField(
        choices=TYPE_DISTRIBUTION,
        initial='TERRAIN',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # Champ pour sélectionner le lot directement
    lot = forms.ModelChoiceField(
        queryset=LotEntrepot.objects.filter(quantite_restante__gt=0),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'lot-select'
        }),
        label="Sélectionner un lot"
    )
    
    specification = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: En poudre, en graine, moulu, etc.',
            'id': 'specification-input'
        }),
        label="Spécification (optionnel)",
        help_text="Forme, présentation ou autre spécification du produit"
    )
    
     
    quantite = forms.DecimalField(
        min_value=0.01,  # ✅ CHANGÉ : 0.01 au lieu de 0.5 pour plus de flexibilité
        max_digits=10,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01',  # ✅ CHANGÉ : 0.01 pour accepter les centimes
            'id': 'quantite-input',
            'min': '0.01',   # ✅ AJOUTÉ : validation HTML
            'placeholder': 'Ex: 1.5 ou 1,5'
        })
    )

    # PRIX OBLIGATOIRES maintenant
    prix_gros = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01',  # ✅ CHANGÉ : 0.01 pour les centimes
            'placeholder': 'Prix gros *',
            'id': 'prix-gros-input',
            'min': '0.01'    # ✅ AJOUTÉ
        }),
        label="Prix gros *"
    )
    
    prix_detail = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'step': '0.01',  
            'placeholder': 'Prix détail *',
            'id': 'prix-detail-input',
            'min': '0.01'    
        }),
        label="Prix détail *"
    )
    
    
    date_distribution = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control datetimepicker',
            'type': 'datetime-local',
            'id': 'date-distribution-input'
        }),
        initial=timezone.now
    )

    class Meta:
        model = DistributionAgent
        fields = ['type_distribution', 'agent_terrain', 'date_distribution']
        widgets = {
            'agent_terrain': forms.Select(attrs={
                'class': 'form-select', 
                'id': 'agent-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Limiter aux agents terrain (sauf pour l'auto-distribution)
        self.fields['agent_terrain'].queryset = Agent.objects.filter(
            type_agent__in=['terrain', 'stagiaire']
        )
        self.fields['agent_terrain'].empty_label = "Sélectionner un agent (terrain ou stagiaire)"
        self.fields['agent_terrain'].required = False
        
        # Filtrer les lots avec stock disponible et précharger les relations
        self.fields['lot'].queryset = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).select_related('produit', 'fournisseur').order_by('produit__nom', 'date_reception')
        
        # Formater la date initiale
        if self.instance and self.instance.pk:
            self.fields['date_distribution'].initial = self.instance.date_distribution.strftime('%Y-%m-%dT%H:%M')
        else:
            self.fields['date_distribution'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        type_distribution = cleaned_data.get('type_distribution')
        agent = cleaned_data.get('agent_terrain')
        lot = cleaned_data.get('lot')
        quantite = cleaned_data.get('quantite')
        prix_gros = cleaned_data.get('prix_gros')
        prix_detail = cleaned_data.get('prix_detail')
    
        # Validation du type de distribution
        if type_distribution in ['TERRAIN', 'STAGIAIRE'] and not agent:
            self.add_error('agent_terrain', 'Un agent est requis pour ce type de distribution.')
    
        if type_distribution == 'STAGIAIRE' and agent:
            if agent.type_agent != 'stagiaire':
                self.add_error('agent_terrain', 'Vous devez sélectionner un stagiaire pour ce type de distribution.')
            elif hasattr(agent, 'date_fin_stage') and agent.date_fin_stage < timezone.now().date():
                self.add_error('agent_terrain', 'Ce stagiaire est expiré.')
    
        elif type_distribution == 'AUTO':
            cleaned_data['agent_terrain'] = None
        
        # Validation du lot et de la quantité
        if lot and quantite:
            if quantite > lot.quantite_restante:
                self.add_error(
                    'quantite', 
                    f'Quantité insuffisante dans ce lot. Stock disponible: {lot.quantite_restante}'
                )
            
            if quantite <= 0:
                self.add_error('quantite', 'La quantité doit être supérieure à 0')
        
        # Validation des prix (OBLIGATOIRES)
        if not prix_gros:
            self.add_error('prix_gros', 'Le prix gros est obligatoire')
        elif prix_gros <= 0:
            self.add_error('prix_gros', 'Le prix gros doit être supérieur à 0')
            
        if not prix_detail:
            self.add_error('prix_detail', 'Le prix détail est obligatoire')
        elif prix_detail <= 0:
            self.add_error('prix_detail', 'Le prix détail doit être supérieur à 0')
            
        # Vérifier que le prix détail est supérieur au prix gros
        if prix_gros and prix_detail and prix_detail <= prix_gros:
            self.add_error('prix_detail', 'Le prix détail doit être supérieur au prix gros')
        
        # Validation de la date
        date_distribution = cleaned_data.get('date_distribution')
        if date_distribution:
            if date_distribution > timezone.now():
                self.add_error('date_distribution', 'La date de distribution ne peut pas être dans le futur')
            
            if lot and date_distribution < lot.date_reception:
                self.add_error(
                    'date_distribution',
                    f'Ce lot n\'était pas encore reçu à cette date. Date de réception: {lot.date_reception.strftime("%d/%m/%Y")}'
                )
        
        return cleaned_data

    def save(self, commit=True):
        from django.db import transaction
    
        instance = super().save(commit=False)
    
        # Récupérer ou créer le superviseur
        superviseur, created = Agent.objects.get_or_create(
            user=self.current_user,
            defaults={'type_agent': 'entrepot'}
        )
        instance.superviseur = superviseur
        instance.type_distribution = self.cleaned_data['type_distribution']
    
        if instance.date_distribution < timezone.now():
            instance.est_retroactive = True
    
        if commit:
            try:
                with transaction.atomic():
                    instance.save()
    
                    lot = self.cleaned_data.get('lot')
                    quantite = self.cleaned_data.get('quantite')
                    prix_gros = self.cleaned_data.get('prix_gros')
                    prix_detail = self.cleaned_data.get('prix_detail')
                    specification = self.cleaned_data.get('specification', '').strip()
                    
                    if lot and quantite:
                        # Créer le détail de distribution
                        detail = DetailDistribution.objects.create(
                            distribution=instance,
                            lot=lot,
                            quantite=quantite,
                            prix_gros=prix_gros,
                            prix_detail=prix_detail,
                            specification=specification

                        )
    
                        # Mettre à jour le stock du lot
                        LotEntrepot.objects.filter(id=lot.id).update(
                            quantite_restante=models.F('quantite_restante') - quantite
                        )
    
                        # Créer le mouvement de stock
                        MouvementStock.objects.create(
                            produit=lot.produit,
                            lot=lot,
                            agent=instance.superviseur,
                            type_mouvement='DISTRIBUTION',
                            quantite=quantite,
                            date_mouvement=instance.date_distribution,
                            detail_distribution=detail
                        )
    
                        # Mettre à jour les totaux
                        instance._mettre_a_jour_totaux()
    
            except Exception as e:
                if instance.pk:
                    instance.delete()
                raise e
    
        return instance
    
class DistributionModificationForm(forms.ModelForm):
    """Formulaire pour modifier une distribution existante"""
    
    raison_modification = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Expliquez la raison de cette modification...',
            'rows': 3
        }),
        label="Raison de la modification"
    )
    
    class Meta:
        model = DistributionAgent
        fields = ['date_distribution']
        widgets = {
            'date_distribution': forms.DateTimeInput(attrs={
                'class': 'form-control datetimepicker',
                'type': 'datetime-local'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Formater la date existante
        if self.instance and self.instance.pk:
            self.fields['date_distribution'].initial = self.instance.date_distribution.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation de la date
        date_distribution = cleaned_data.get('date_distribution')
        if date_distribution and date_distribution > timezone.now():
            self.add_error('date_distribution', 'La date de distribution ne peut pas être dans le futur')
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            # La logique de mise à jour des totaux sera gérée par la vue
        
        return instance

class DistributionSuppressionForm(forms.Form):
    """Formulaire pour supprimer une distribution"""
    
    raison_suppression = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Expliquez la raison de cette suppression...',
            'rows': 3
        }),
        label="Raison de la suppression"
    )
    
    confirmer_suppression = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Je confirme vouloir supprimer cette distribution"
    )

    def clean(self):
        cleaned_data = super().clean()
        confirmer_suppression = cleaned_data.get('confirmer_suppression')
        
        if not confirmer_suppression:
            self.add_error('confirmer_suppression', 'Vous devez confirmer la suppression')
        
        return cleaned_data

# === FORMULAIRE VENTE ===
# === FORMULAIRE VENTE ===
class VenteForm(forms.ModelForm):
    # Nouveau client (optionnel)
    nouveau_client = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    client_nom = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du client (optionnel)'
        })
    )
    client_contact = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Contact (téléphone, optionnel)'
        })
    )
    client_type = forms.ChoiceField(
        choices=Client.TYPE_CLIENT_CHOICES,
        required=False,
        initial='detail',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Type de vente
    type_vente = forms.ChoiceField(
        choices=Vente.TYPE_VENTE_CHOICES,
        initial='detail',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'type-vente'
        }),
        help_text="Choisissez le type de vente (gros ou détail)"
    )
    
    # Mode de paiement
    mode_paiement = forms.ChoiceField(
        choices=Vente.MODE_PAIEMENT_CHOICES,
        initial='comptant',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'mode-paiement'
        }),
        help_text="Choisissez le mode de paiement"
    )

    # Date de vente rétroactive
    date_vente = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'date-vente'
        }),
        initial=timezone.now,
        label="Date de la vente",
        help_text="Date à laquelle la vente a été effectuée"
    )

    # ✅ MODIFIÉ : Champ stagiaire optionnel - TOUS les stagiaires
    stagiaire = forms.ModelChoiceField(
        queryset=Agent.objects.none(),  # Sera rempli dans __init__
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'stagiaire-select'
        }),
        label="Stagiaire (optionnel)",
        help_text="Si cette vente a été réalisée par un stagiaire"
    )

    class Meta:
        model = Vente
        fields = ['detail_distribution', 'quantite', 'type_vente', 'mode_paiement', 'prix_vente_unitaire', 'date_vente', 'stagiaire']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select', 'id': 'client-existant'}),
            'detail_distribution': forms.Select(attrs={'class': 'form-select', 'id': 'detail-distribution'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'id': 'quantite-vente'}),
            'prix_vente_unitaire': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01', 
                'id': 'prix-vente',
                'readonly': 'readonly',
                'placeholder': 'Le prix sera déterminé automatiquement'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        # Rendre tous les champs non obligatoires sauf ceux nécessaires
        self.fields['detail_distribution'].required = False
        self.fields['quantite'].required = False
        self.fields['type_vente'].required = True
        self.fields['mode_paiement'].required = True
        self.fields['prix_vente_unitaire'].required = False
        self.fields['date_vente'].required = True
        self.fields['stagiaire'].required = False
        
        # Formater la date initiale pour le champ datetime-local
        if self.instance and self.instance.pk:
            self.fields['date_vente'].initial = self.instance.date_vente.strftime('%Y-%m-%dT%H:%M')
        else:
            self.fields['date_vente'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')
        
        # ✅ Tous les stagiaires, même expirés
        if self.agent:
            tous_les_stagiaires = Agent.objects.filter(type_agent='stagiaire').select_related('user')
            self.fields['stagiaire'].queryset = tous_les_stagiaires
            self.fields['stagiaire'].label_from_instance = lambda obj: (
                f"{obj.full_name} (Expire le {obj.date_expiration.strftime('%d/%m/%Y')})"
                if obj.date_expiration else f"{obj.full_name} (Pas de date d'expiration)"
            )
        
        # Filtrer les clients existants
        self.fields['client'] = forms.ModelChoiceField(
            queryset=Client.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select', 'id': 'client-existant'}),
            empty_label="Sélectionner un client existant (optionnel)..."
        )        
        # ✅ APPROCHE CALCUL DYNAMIQUE
        from django.db.models import DecimalField, Sum, F, Value, ExpressionWrapper
        from django.db.models.functions import Coalesce

        if self.agent:
            detail_qs = DetailDistribution.objects.filter(
                distribution__agent_terrain=self.agent,
                distribution__est_supprime=False,
                est_supprime=False
            ).annotate(
                quantite_vendue_calculee=Coalesce(
                    Sum('vente__quantite'), 
                    Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))
                )
            ).annotate(
                quantite_restante=ExpressionWrapper(
                    F('quantite') - F('quantite_vendue_calculee'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ).filter(
                quantite_restante__gt=0
            ).select_related('lot__produit', 'lot')

            self.fields['detail_distribution'].queryset = detail_qs

    def label_from_distribution(self, obj):
        """Format correct pour l'affichage des options"""
        produit = obj.lot.produit.nom
        lot_ref = obj.lot.reference_lot or f"Lot#{obj.lot.id}"
        
        # ✅ FORCER le calcul de la quantité restante
        if hasattr(obj, 'quantite_restante'):
           quantite_dispo = getattr(obj, 'quantite_restante', None)

        else:
            # Calcul manuel si l'annotation n'est pas disponible
            from django.db.models import Sum
            quantite_vendue = obj.vente_set.aggregate(
                total=Sum('quantite')
            )['total'] or 0
            quantite_dispo = obj.quantite - quantite_vendue
        
        specification = f" - {obj.specification}" if obj.specification else ""
        
        return f"{produit}{specification} - {lot_ref} (Stock dispo: {quantite_dispo})"
    def clean(self):
        cleaned_data = super().clean()
        
        # Validation client - TOUT EST OPTIONNEL
        if cleaned_data.get('nouveau_client') and cleaned_data.get('client_nom'):
            if not cleaned_data.get('client_nom'):
                self.add_error('client_nom', 'Nom requis si vous créez un nouveau client')
        
        # Validation de base (produit et quantité)
        if not cleaned_data.get('detail_distribution'):
            self.add_error('detail_distribution', 'Produit à vendre requis')
        
        if not cleaned_data.get('quantite') or cleaned_data.get('quantite', 0) <= 0:
            self.add_error('quantite', 'Quantité valide requise')
        
        # ✅ Vérifier la quantité disponible AVEC LE CALCUL DYNAMIQUE
        if cleaned_data.get('detail_distribution') and cleaned_data.get('quantite'):
            detail = cleaned_data['detail_distribution']
            
            # Calculer la quantité déjà vendue
            from django.db.models import Sum
            quantite_vendue = detail.vente_set.aggregate(
                total=Sum('quantite')
            )['total'] or 0
            
            quantite_disponible = detail.quantite - quantite_vendue
            
            if cleaned_data['quantite'] > quantite_disponible:
                self.add_error('quantite', f'Quantité insuffisante. Disponible: {quantite_disponible}')
        
        # Validation de la date de vente
        date_vente = cleaned_data.get('date_vente')
        if date_vente and date_vente > timezone.now():
            self.add_error('date_vente', 'La date de vente ne peut pas être dans le futur')
        
        # Validation stagiaire
        stagiaire = cleaned_data.get('stagiaire')
        if stagiaire:
            if stagiaire.type_agent != 'stagiaire':
                self.add_error('stagiaire', "L'agent sélectionné doit être un stagiaire")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Associer l'agent
        instance.agent = self.agent

        # Associer le stagiaire si sélectionné
        stagiaire = self.cleaned_data.get('stagiaire')
        if stagiaire:
            instance.stagiaire = stagiaire

        # Gérer le client
        if self.cleaned_data.get('nouveau_client') and self.cleaned_data.get('client_nom'):
            client = Client.objects.create(
                nom=self.cleaned_data['client_nom'],
                contact=self.cleaned_data.get('client_contact', ''),
                type_client=self.cleaned_data.get('client_type', 'detail')
            )
            instance.client = client
        elif self.cleaned_data.get('client'):
            instance.client = self.cleaned_data.get('client')
        else:
            instance.client = None

        # Déterminer automatiquement le prix
        if not instance.prix_vente_unitaire and instance.detail_distribution:
            if instance.type_vente == 'gros':
                instance.prix_vente_unitaire = instance.detail_distribution.prix_gros
            else:
                instance.prix_vente_unitaire = instance.detail_distribution.prix_detail

        if commit:
            instance.save()
            # ✅ NE RIEN FAIRE - la quantité disponible est calculée dynamiquement
            
        return instance

# === FORMULAIRE DETTE (pour vente à crédit) ===
class DetteForm(forms.ModelForm):

    # Informations de localisation
    nom_localite = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Grand Marché Central, Boutique XYZ...'
        }),
        help_text="Nom du lieu où la dette a été contractée"
    )
    
    date_echeance = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().date().isoformat()
        }),
        help_text="Date d'échéance pour le remboursement"
    )
    

    class Meta:
        model = Dette
        fields = ['nom_localite', 'date_echeance',  'notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notes supplémentaires...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.vente = kwargs.pop('vente', None)
        super().__init__(*args, **kwargs)
        
        # Définir la date d'échéance par défaut à 30 jours
        
        if not self.instance.pk:
            self.fields['date_echeance'].initial = timezone.now().date() + timedelta(days=7)

    def clean_date_echeance(self):
        date_echeance = self.cleaned_data['date_echeance']
        if date_echeance < timezone.now().date():
            raise forms.ValidationError("La date d'échéance ne peut pas être dans le passé")
        return date_echeance

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.vente:
            instance.vente = self.vente
            instance.montant_total = self.vente.total_vente
            instance.montant_restant = self.vente.total_vente
        
        if commit:
            instance.save()
            
        return instance
    
# === FORMULAIRE PAIEMENT DETTE ===
class PaiementDetteForm(forms.ModelForm):
    montant = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Montant du paiement'
        })
    )
    
    mode_paiement = forms.ChoiceField(
        choices=PaiementDette.MODE_PAIEMENT_CHOICES,
        initial='espece',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = PaiementDette
        fields = ['montant', 'mode_paiement', 'reference', 'notes']
        widgets = {
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Référence du paiement (numéro chèque, etc.)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes sur le paiement...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.dette = kwargs.pop('dette', None)
        super().__init__(*args, **kwargs)
        
        if self.dette:
            # Définir le montant maximum possible
            montant_max = self.dette.montant_restant
            self.fields['montant'].widget.attrs['max'] = str(montant_max)
            self.fields['montant'].help_text = f"Montant restant: {montant_max} FCFA"

    def clean_montant(self):
        montant = self.cleaned_data['montant']
        if self.dette and montant > self.dette.montant_restant:
            raise forms.ValidationError(
                f"Le montant ne peut pas dépasser le reste dû ({self.dette.montant_restant} FCFA)"
            )
        return montant

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.dette:
            instance.dette = self.dette
        
        if commit:
            instance.save()
            
        return instance

# === FORMULAIRE BONUS AGENT (consultation) ===
class BonusAgentForm(forms.ModelForm):
    class Meta:
        model = BonusAgent
        fields = []  # Formulaire en lecture seule pour consultation
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Rendre tous les champs en lecture seule
        for field in self.fields:
            self.fields[field].widget.attrs['readonly'] = True
            self.fields[field].widget.attrs['class'] = 'form-control-plaintext'

# === FORMULAIRE RAPPORT DETTES ===
class RapportDettesForm(forms.Form):
    STATUT_CHOICES = (
        ('', 'Tous les statuts'),
        ('en_cours', 'En cours'),
        ('partiellement_paye', 'Partiellement payé'),
        ('paye', 'Payé'),
        ('en_retard', 'En retard'),
    )
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Date de début"
    )
    
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Date de fin"
    )
    
    statut = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Statut de la dette"
    )
    
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(type_agent='terrain'),
        required=False,
        empty_label="Tous les agents",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Agent terrain"
    )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin and date_debut > date_fin:
            self.add_error('date_fin', "La date de fin ne peut pas être avant la date de début")
            
        return cleaned_data

# === FORMULAIRE RECOUVREMENT ===


class RecouvrementForm(forms.ModelForm):
    vente = forms.ModelChoiceField(
        queryset=Vente.objects.none(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Sélectionner la vente à recouvrer"
    )

    date_recouvrement = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date du recouvrement",
        initial=timezone.now().date()
    )
    
    class Meta:
        model = Recouvrement
        fields = ['vente','montant_recouvre', 'date_recouvrement', 'commentaire']
        widgets = {
            'montant_recouvre': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ex: Recouvrement partiel, paiement en espèces...'
            }),
        }
        labels = {
            'vente': 'Vente associée',
            'montant_recouvre': 'Montant à recouvrir',
            'commentaire': 'Commentaire (facultatif)',
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        self.superviseur = kwargs.pop('superviseur', None)
        super().__init__(*args, **kwargs)
        
        if self.agent:
            # Filtrer les ventes selon la règle métier
            queryset = Vente.objects.filter(
                agent=self.agent,
                ancienne_vente=False 
            )
            
            # Pour superviseur recouvrant un agent terrain
            if self.superviseur and self.superviseur.id != self.agent.id:
                # VENTES COMPTANT : toujours recouvrables
                ventes_comptant = queryset.filter(mode_paiement='comptant')
                
                # VENTES CRÉDIT : seulement si TOTALEMENT payées
                ventes_credit = queryset.filter(
                    mode_paiement='credit',
                    dette__montant_restant=0  # Dette totalement recouvrée
                )
                
                # Combiner les deux querysets
                self.fields['vente'].queryset = ventes_comptant | ventes_credit
            else:
                # AUTO-RECOUVREMENT : toutes les ventes non anciennes
                self.fields['vente'].queryset = queryset

    def clean_vente(self):
        vente = self.cleaned_data.get('vente')
        if not vente:
            raise forms.ValidationError("Veuillez sélectionner une vente.")

        if vente.agent != self.agent:
            raise forms.ValidationError("Cette vente n'appartient pas à l'agent.")

        # Vérifier que c'est une vente NON ancienne
        if vente.ancienne_vente:
            raise forms.ValidationError(
                "Les ventes anciennes ne peuvent pas être recouvrées."
            )

        # Vérification spécifique pour le recouvrement superviseur → agent terrain
        if self.superviseur and self.superviseur.id != self.agent.id:
            if vente.mode_paiement == 'credit':
                if hasattr(vente, 'dette') and vente.dette.montant_restant > 0:
                    raise forms.ValidationError(
                        "Cette dette n'est pas encore totalement recouvrée par l'agent auprès du client. "
                        "Le superviseur ne peut recouvrir que les dettes entièrement recouvrées."
                    )

        return vente
    
    def clean_montant_recouvre(self):
        montant = self.cleaned_data.get('montant_recouvre')
        
        if self.agent and montant > self.agent.argent_en_possession:
            raise forms.ValidationError(
                f"L'agent n'a que {self.agent.argent_en_possession} FCFA en sa possession."
            )
        
        if montant <= 0:
            raise forms.ValidationError("Le montant doit être supérieur à 0.")
            
        return montant

    def clean_date_recouvrement(self):
        date_recouvrement = self.cleaned_data.get('date_recouvrement')
        
        # Empêcher les dates futures
        if date_recouvrement > timezone.now().date():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
            
        return date_recouvrement

    def clean(self):
        cleaned_data = super().clean()
        vente = cleaned_data.get('vente')
        montant = cleaned_data.get('montant_recouvre')
        
        if vente and montant:
            # Vérification pour les superviseurs recouvrant des agents terrain
            if (self.superviseur and self.superviseur.id != self.agent.id and 
                vente.mode_paiement == 'credit' and hasattr(vente, 'dette')):
                
                if vente.dette.montant_restant > 0:
                    raise forms.ValidationError(
                        f"Impossible de recouvrir cette vente à crédit. "
                        f"La dette chez le client n'est pas encore totalement recouvrée "
                        f"(reste {vente.dette.montant_restant} FCFA à recouvrir)."
                    )
        
        return cleaned_data
  
    # --------------------------
    # SAUVEGARDE AVEC LOGIQUE BONUS
    # --------------------------

    def save(self, commit=True):
        recouvrement = super().save(commit=False)
        vente = self.cleaned_data['vente']
        montant = self.cleaned_data['montant_recouvre']
    
        if self.agent:
            recouvrement.agent = self.agent
    
        recouvrement.vente = vente
    
        if commit:
            recouvrement.save()
    
        # 2️⃣ Mise à jour dette si crédit
        if vente.mode_paiement == 'credit' and hasattr(vente, 'dette') and vente.dette:
            dette = vente.dette
            dette.montant_restant = max(Decimal('0.00'), dette.montant_restant - montant)
            dette.save()
    
        # 3️⃣ Bonus 48h
        recouvrement.calculer_bonus()
    
        # 4️⃣ Marquer la vente comme ANCIENNE si totalement recouvrée
        if vente.mode_paiement == 'comptant':
            vente.ancienne_vente = True
            vente.save(update_fields=['ancienne_vente'])
    
        elif vente.mode_paiement == 'credit' and hasattr(vente, 'dette'):
            if vente.dette.montant_restant == 0:
                vente.ancienne_vente = True
                vente.save(update_fields=['ancienne_vente'])
    
        return recouvrement
    
# forms.py
# forms.py

class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = ['montant', 'fichier_facture', 'description']
        widgets = {
            'montant': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'placeholder': 'Montant versé à la banque'
            }),
            'fichier_facture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Description du versement'
            }),
        }

from tinymce.widgets import TinyMCE
from tinymce.widgets import TinyMCE


class VersementForm(forms.ModelForm):
    # Dépense optionnelle intégrée
    depense_montant = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=0,
        label="Montant de la dépense",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    depense_description = forms.CharField(
        required=False,
        label="Description de la dépense",
        widget=TinyMCE(attrs={
            'cols': 5,
            'rows': 4,
            'style': 'min-height: 60px; width:100%; max-width:100%;'
        })
    )
    
    # Champ pour plusieurs reçus - APPROCHE SIMPLE
    recus = forms.FileField(
        required=False,
        label="Reçus de versement",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        }),
        help_text="Maintenez Ctrl pour sélectionner plusieurs fichiers"
    )

    recus_description = forms.CharField(
        required=False,
        label="Description des reçus",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Description générale pour tous les reçus...'
        })
    )

    class Meta:
        model = VersementBancaire
        fields = [
            'montant_vente',
            'montant_hors_vente',
            'description',
            'date_versement_reelle',
        ]
        widgets = {
            'montant_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'montant_hors_vente': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': TinyMCE(attrs={
                'rows': 2,
                'class': 'form-control'
            }), 
            'date_versement_reelle': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajout de placeholder pour une meilleure UX mobile
        self.fields['montant_vente'].widget.attrs['placeholder'] = '0.00'
        self.fields['montant_hors_vente'].widget.attrs['placeholder'] = '0.00'
        self.fields['depense_montant'].widget.attrs['placeholder'] = '0.00'

    def save(self, superviseur=None, commit=True):
        """
        Sauvegarde qui gère création / modification
        - Dépense mise à jour si elle existe
        - Plusieurs reçus
        """
        versement = super().save(commit=False)

        # Affectation superviseur seulement en création
        if superviseur is not None:
            versement.superviseur = superviseur

        if commit:
            versement.save()

            # ============================
            # 🔥 GESTION DES DÉPENSES
            # ============================
            dep_montant = self.cleaned_data.get('depense_montant') or 0
            dep_desc = (self.cleaned_data.get('depense_description') or "").strip()

            has_description = bool(dep_desc)
            has_amount = dep_montant > 0

            # Récupération éventuelle d'une dépense existante
            depense_existante = versement.depenses.first()

            # Si l'utilisateur a saisi une dépense
            if has_description or has_amount:

                # Valeurs par défaut si partiellement remplies
                if has_amount and not dep_desc:
                    dep_desc = "Dépense associée au versement"
                if not has_amount:
                    dep_montant = 0

                if depense_existante:
                    # 🔄 Mise à jour de la dépense existante
                    depense_existante.montant = dep_montant
                    depense_existante.description = dep_desc
                    depense_existante.save()
                else:
                    # ✨ Création d'une nouvelle dépense
                    Depense.objects.create(
                        versement=versement,
                        montant=dep_montant,
                        description=dep_desc
                    )

            else:
                # L'utilisateur supprime les champs -> supprimer la dépense existante
                if depense_existante:
                    depense_existante.delete()

            # ============================
            # 📂 GESTION DES RÉCUS MULTIPLES
            # ============================
            recus_files = self.files.getlist('recus')
            recus_description = (self.cleaned_data.get('recus_description') or "").strip()

            for recu_file in recus_files:
                RecuVersement.objects.create(
                    versement=versement,
                    fichier=recu_file,
                    description=recus_description or f"Reçu pour versement {versement.id}"
                )

        return versement

class RecuVersementForm(forms.Form):  # ✅ Utiliser Form au lieu de ModelForm
    versement = forms.ModelChoiceField(
        queryset=VersementBancaire.objects.all(),
        required=False,
        label="Versement associé",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    fichiers = MultiFileField(
        required=True,  # ✅ Changer à True pour rendre obligatoire
        label="Fichiers reçus",
        widget=MultiFileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        }),
        help_text="Sélectionnez un ou plusieurs fichiers (Ctrl + clic)"
    )

    description_generale = forms.CharField(
        required=False,
        label="Description",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': "Description commune pour tous les reçus"
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optionnel: filtrer les versements si nécessaire
        # self.fields['versement'].queryset = VersementBancaire.objects.filter(...)

    def save(self):
        
        description = (self.cleaned_data.get('description_generale') or "").strip()
        fichiers = self.cleaned_data['fichiers']

        recus_crees = []
        for fichier in fichiers:
            recu = RecuVersement.objects.create(
               
                fichier=fichier,
                description=description or f"Reçu pour versement "
            )
            recus_crees.append(recu)

        return recus_crees
    