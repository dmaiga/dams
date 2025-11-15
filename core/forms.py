from django import forms
from datetime import datetime
from django.utils import timezone
from .models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,Dette,PaiementDette,
    DistributionAgent, Agent, DetailDistribution, Facture,BonusAgent,
    MouvementStock,Recouvrement,VersementBancaire,Fournisseur,Depense
)
from django.db import models
import os

# forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Agent
from django.core.exceptions import ValidationError

# forms.py
from django import forms
from django.contrib.auth.models import User
from .models import Agent
from django.core.exceptions import ValidationError

# forms.py
from django import forms
from django.utils import timezone
from .models import VersementBancaire, Depense
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from decimal import Decimal

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
            'step': '0.01',   
            'min': '0.01',
            'placeholder': 'Quantité'
             }),
            'prix_achat_unitaire': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
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
        
        prix = cleaned_data.get('prix_achat_unitaire')
        if not prix or prix <= 0:
            self.add_error('prix_achat_unitaire', 'Le prix d\'achat doit être supérieur à 0')
        
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
        ('TERRAIN', 'Distribution à un agent '),
        ('AUTO', 'Auto-distribution'),
        ('STAGIAIRE', 'Distribution à un stagiaire'),
    )
    
    type_distribution = forms.ChoiceField(
        choices=TYPE_DISTRIBUTION,
        initial='TERRAIN',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # Champs dynamiques pour les produits
    produit = forms.ModelChoiceField(
        queryset=Produit.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantite = forms.IntegerField(
        min_value=1,
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'quantite-input'})
    )
    prix_gros = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix gros'})
    )
    prix_detail = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Prix détail'})
    )
    
    date_distribution = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control datetimepicker',
            'type': 'datetime-local'
        }),
        initial=timezone.now
    )

    class Meta:
        model = DistributionAgent
        fields = ['type_distribution', 'agent_terrain', 'date_distribution']
        widgets = {
            'agent_terrain': forms.Select(attrs={'class': 'form-select', 'id': 'agent-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Limiter aux agents terrain (sauf pour l'auto-distribution)
        self.fields['agent_terrain'].queryset = Agent.objects.filter(type_agent__in=['terrain', 'stagiaire'])
        self.fields['agent_terrain'].empty_label = "Sélectionner un agent (terrain ou stagiaire)"
        self.fields['agent_terrain'].required = False
        
        # Filtrer les produits qui ont du stock disponible
        produits_avec_stock = []
        for produit in Produit.objects.all():
            if LotEntrepot.get_lots_disponibles(produit.nom).exists():
                produits_avec_stock.append(produit)
        
        self.fields['produit'].queryset = Produit.objects.filter(
            id__in=[p.id for p in produits_avec_stock]
        )
        
        # Formater la date initiale
        if self.instance and self.instance.pk:
            self.fields['date_distribution'].initial = self.instance.date_distribution.strftime('%Y-%m-%dT%H:%M')
        else:
            self.fields['date_distribution'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        type_distribution = cleaned_data.get('type_distribution')
        agent = cleaned_data.get('agent_terrain')
    
        if type_distribution in ['TERRAIN', 'STAGIAIRE'] and not agent:
            self.add_error('agent_terrain', 'Un agent est requis pour ce type de distribution.')
    
        if type_distribution == 'STAGIAIRE' and agent:
            if agent.type_agent != 'stagiaire':
                self.add_error('agent_terrain', 'Vous devez sélectionner un stagiaire pour ce type de distribution.')
            elif hasattr(agent, 'date_fin_stage') and agent.date_fin_stage < timezone.now().date():
                self.add_error('agent_terrain', 'Ce stagiaire est expiré.')
    
        elif type_distribution == 'AUTO':
            # Pour l'auto-distribution, pas besoin d'agent_terrain
            cleaned_data['agent_terrain'] = None
        
        # Validation commune
        if not cleaned_data.get('produit'):
            self.add_error('produit', 'Produit requis')
        if not cleaned_data.get('quantite') or cleaned_data.get('quantite', 0) <= 0:
            self.add_error('quantite', 'Quantité valide requise')
        
        # Validation de la date
        date_distribution = cleaned_data.get('date_distribution')
        if date_distribution:
            if date_distribution > timezone.now():
                self.add_error('date_distribution', 'La date de distribution ne peut pas être dans le futur')
        
        # Vérifier le stock disponible
        if cleaned_data.get('produit') and cleaned_data.get('quantite') and cleaned_data.get('date_distribution'):
            produit_nom = cleaned_data['produit'].nom
            quantite_demandee = cleaned_data['quantite']
            stock_disponible = self.get_stock_a_date(produit_nom, cleaned_data['date_distribution'])
            
            if quantite_demandee > stock_disponible:
                self.add_error('quantite', f'Stock insuffisant à cette date. Disponible: {stock_disponible} unités')
            
        return cleaned_data

    def get_stock_a_date(self, produit_nom, date_reference):
        """
        Calcule le stock disponible à une date donnée - version optimisée
        """
        from django.db.models import Sum
        
        # Stock total initial (lots reçus avant la date de référence)
        stock_total_initial = LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            date_reception__lte=date_reference
        ).aggregate(total=Sum('quantite_initiale'))['total'] or 0
        
        # Quantité déjà distribuée avant cette date
        quantite_deja_distribuee = DetailDistribution.objects.filter(
            lot__produit__nom=produit_nom,
            distribution__date_distribution__lte=date_reference,
            distribution__est_supprime=False,
            est_supprime=False
        ).aggregate(total=Sum('quantite'))['total'] or 0
        
        return stock_total_initial - quantite_deja_distribuee
    

    def get_lots_disponibles_a_date(self, produit_nom, date_reference):
        """Retourne les lots disponibles à une date donnée en VRAI FIFO"""
        from django.db.models import Sum

        lots = LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            date_reception__lte=date_reference
        ).order_by('date_reception', 'id')  # FIFO = plus ancienne date d'abord

        lots_avec_stock = []
        for lot in lots:
            # ✅ CORRECTION : Calculer la quantité déjà distribuée de CE LOT avant la date de référence
            quantite_distribuee = DetailDistribution.objects.filter(
                lot=lot,  # ✅ Important : filtrer par LOT spécifique
                distribution__date_distribution__lte=date_reference,
                distribution__est_supprime=False,  # ✅ Ignorer les distributions supprimées
                est_supprime=False  # ✅ Ignorer les détails supprimés
            ).aggregate(total=Sum('quantite'))['total'] or 0

            quantite_restante = lot.quantite_initiale - quantite_distribuee

            # ✅ CORRECTION : Ne garder que les lots qui ont encore du stock
            if quantite_restante > 0:
                lot._quantite_restante_calculee = quantite_restante
                lots_avec_stock.append(lot)

        return lots_avec_stock
    
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
    
                    produit = self.cleaned_data.get('produit')
                    quantite_demandee = self.cleaned_data.get('quantite')
                    prix_gros = self.cleaned_data.get('prix_gros')
                    prix_detail = self.cleaned_data.get('prix_detail')
    
                    if produit and quantite_demandee:
                        lots_disponibles = self.get_lots_disponibles_a_date(produit.nom, instance.date_distribution)
                        quantite_restante = quantite_demandee
    
                        # VÉRIFICATION FINALE DU STOCK
                        stock_total_disponible = sum(lot._quantite_restante_calculee for lot in lots_disponibles)
    
                        if quantite_demandee > stock_total_disponible:
                            raise forms.ValidationError(
                                f"Stock insuffisant pour {produit.nom}. "
                                f"Demandé: {quantite_demandee}, Disponible: {stock_total_disponible}"
                            )
    
                        details_creation = []
                        mouvements_creation = []
                        lots_a_mettre_a_jour = []
    
                        for lot in lots_disponibles:
                            if quantite_restante <= 0:
                                break
                            
                            quantite_a_prelever = min(quantite_restante, lot._quantite_restante_calculee)
    
                            # Vérifier le stock actuel du lot
                            lot_actuel = LotEntrepot.objects.get(id=lot.id)
                            if quantite_a_prelever > lot_actuel.quantite_restante:
                                quantite_a_prelever = lot_actuel.quantite_restante
    
                            if quantite_a_prelever <= 0:
                                continue
                            
                            # ✅ CORRECTION : Créer un DetailDistribution POUR CHAQUE LOT
                            details_creation.append(DetailDistribution(
                                distribution=instance,
                                lot=lot,
                                quantite=quantite_a_prelever,  # Quantité spécifique à ce lot
                                prix_gros=prix_gros,           # Même prix pour tous les lots du même produit
                                prix_detail=prix_detail        # Même prix pour tous les lots du même produit
                            ))
    
                            # Préparer la mise à jour du lot
                            lots_a_mettre_a_jour.append((lot.id, quantite_a_prelever))
    
                            # Préparer le mouvement de stock
                            mouvements_creation.append(MouvementStock(
                                produit=produit,
                                lot=lot,
                                agent=instance.superviseur,
                                type_mouvement='DISTRIBUTION',
                                quantite=quantite_a_prelever,
                                date_mouvement=instance.date_distribution
                            ))
    
                            quantite_restante -= quantite_a_prelever
    
                        if quantite_restante > 0:
                            raise forms.ValidationError(
                                f"Stock insuffisant pour {produit.nom}. "
                                f"Manquant: {quantite_restante} unités"
                            )
    
                        # CRÉATION EN MASSE DES DÉTAILS
                        DetailDistribution.objects.bulk_create(details_creation)
    
                        # MISE À JOUR DES LOTS
                        for lot_id, quantite in lots_a_mettre_a_jour:
                            LotEntrepot.objects.filter(id=lot_id).update(
                                quantite_restante=models.F('quantite_restante') - quantite
                            )
    
                        # CRÉATION DES MOUVEMENTS DE STOCK
                        MouvementStock.objects.bulk_create(mouvements_creation)
    
                        # Mettre à jour les totaux
                        instance._mettre_a_jour_totaux()
    
            except Exception as e:
                # En cas d'erreur, tout est annulé automatiquement par la transaction
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
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'quantite-vente'}),
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
        
        # ✅ MODIFIÉ : TOUS LES STAGIAIRES (sans filtre de date d'expiration)
        if self.agent:
            # Tous les stagiaires, même expirés
            tous_les_stagiaires = Agent.objects.filter(type_agent='stagiaire').select_related('user')
            
            self.fields['stagiaire'].queryset = tous_les_stagiaires
            
            # Formater l'affichage des stagiaires avec indication d'expiration
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
        
        # Filtrer les détails de distribution disponibles pour cet agent
        if self.agent:
            self.fields['detail_distribution'].queryset = DetailDistribution.objects.filter(
                distribution__agent_terrain=self.agent,
                quantite__gt=0  # Seulement les distributions avec du stock disponible
            ).select_related('lot', 'lot__produit')
            
            # Ajouter des informations utiles dans l'affichage
            self.fields['detail_distribution'].label_from_instance = lambda obj: (
                f"{obj.lot.produit.nom} - Lot {obj.lot.reference_lot} - "
                f"Stock: {obj.quantite} - "
                f"Prix gros: {obj.prix_gros or 'N/D'} FCFA - "
                f"Prix détail: {obj.prix_detail or 'N/D'} FCFA"
            )

        # Initialiser les champs comme désactivés
        self.fields['client'].widget.attrs['disabled'] = True
        self.fields['client_nom'].widget.attrs['disabled'] = True
        self.fields['client_contact'].widget.attrs['disabled'] = True
        self.fields['client_type'].widget.attrs['disabled'] = True

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation client - TOUT EST OPTIONNEL
        # Si nouveau client est coché, valider les champs correspondants
        if cleaned_data.get('nouveau_client'):
            if cleaned_data.get('client_nom'):
                # Valider seulement si un nom est saisi
                if not cleaned_data.get('client_nom'):
                    self.add_error('client_nom', 'Nom requis si vous créez un nouveau client')
        # Aucune validation pour les clients existants ou inconnus
        
        # Validation de base (produit et quantité)
        if not cleaned_data.get('detail_distribution'):
            self.add_error('detail_distribution', 'Produit à vendre requis')
        
        if not cleaned_data.get('quantite') or cleaned_data.get('quantite', 0) <= 0:
            self.add_error('quantite', 'Quantité valide requise')
        
        # Vérifier la quantité disponible
        if cleaned_data.get('detail_distribution') and cleaned_data.get('quantite'):
            detail = cleaned_data['detail_distribution']
            if cleaned_data['quantite'] > detail.quantite:
                self.add_error('quantite', f'Quantité insuffisante. Disponible: {detail.quantite}')
        
        # Validation de la date de vente
        date_vente = cleaned_data.get('date_vente')
        if date_vente and date_vente > timezone.now():
            self.add_error('date_vente', 'La date de vente ne peut pas être dans le futur')
        
        # ✅ MODIFIÉ : Validation stagiaire plus permissive
        stagiaire = cleaned_data.get('stagiaire')
        if stagiaire:
            if stagiaire.type_agent != 'stagiaire':
                self.add_error('stagiaire', "L'agent sélectionné doit être un stagiaire")
            # SUPPRIMÉ : Plus de vérification d'expiration
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Associer l'agent (tuteur situationnel)
        instance.agent = self.agent

        # ✅ ASSOCIER LE STAGIAIRE SI SELECTIONNE (même expiré)
        stagiaire = self.cleaned_data.get('stagiaire')
        if stagiaire:
            instance.stagiaire = stagiaire

        # Gérer le client - TOUT EST OPTIONNEL
        if self.cleaned_data.get('nouveau_client') and self.cleaned_data.get('client_nom'):
            # Créer un nouveau client seulement si le nom est fourni
            client = Client.objects.create(
                nom=self.cleaned_data['client_nom'],
                contact=self.cleaned_data.get('client_contact', ''),
                type_client=self.cleaned_data.get('client_type', 'detail')
            )
            instance.client = client
        elif self.cleaned_data.get('client'):
            # Utiliser le client existant sélectionné
            instance.client = self.cleaned_data.get('client')
        else:
            # Aucun client associé → sera "Inconnu"
            instance.client = None

        # Déterminer automatiquement le prix si non fourni
        if not instance.prix_vente_unitaire and instance.detail_distribution:
            if instance.type_vente == 'gros':
                instance.prix_vente_unitaire = instance.detail_distribution.prix_gros
            else:
                instance.prix_vente_unitaire = instance.detail_distribution.prix_detail

        if commit:
            instance.save()
            
            # Mettre à jour la quantité restante dans le détail de distribution
            detail = instance.detail_distribution
            detail.quantite -= instance.quantite
            detail.save()
            
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
    
    delai_bonus_heures = forms.IntegerField(
        required=False,
        initial=48,
        min_value=1,
        max_value=168,  # 7 jours max
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '48'
        }),
        help_text="Délai en heures pour bénéficier du bonus (défaut: 48h)"
    )

    class Meta:
        model = Dette
        fields = ['nom_localite', 'date_echeance', 'delai_bonus_heures', 'notes']
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
            self.fields['date_echeance'].initial = timezone.now().date() + timedelta(days=30)

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
    date_recouvrement = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Date du recouvrement",
        initial=timezone.now().date()
    )
    
    class Meta:
        model = Recouvrement
        fields = ['montant_recouvre', 'date_recouvrement', 'commentaire']
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
            'montant_recouvre': 'Montant à recouvrir',
            'commentaire': 'Commentaire (facultatif)',
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        if self.agent:
            # Ajouter une validation dynamique du montant maximum
            self.fields['montant_recouvre'].widget.attrs['max'] = self.agent.argent_en_possession

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
   



# forms.py
class VersementAvecDepensesForm(forms.ModelForm):
    """Formulaire unique qui combine versement et dépenses"""
    
    # Champs pour les dépenses (optionnels)
    montant_depenses = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        }),
        label="Total des dépenses",
        help_text="Montant total des dépenses associées à ce versement"
    )
    
    description_depenses = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Détail des dépenses effectuées...'
        }),
        label="Détail des dépenses"
    )
    
    categorie_depenses = forms.ChoiceField(
        choices=Depense.CATEGORIE_DEPENSE_CHOICES,
        required=False,
        initial='autres',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Catégorie des dépenses"
    )
    
    date_depenses = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        label="Date des dépenses",
        help_text="Date à laquelle les dépenses ont été effectuées"
    )
    
    justificatif_depenses = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf,.doc,.docx'
        }),
        label="Justificatif des dépenses"
    )

    class Meta:
        model = VersementBancaire
        fields = [
            'type_versement',
            'montant_verse', 
            'details_depenses',
            'date_versement_reelle'
        ]
        widgets = {
            'type_versement': forms.Select(attrs={
                'class': 'form-control',
                'id': 'type_versement_select'
            }),
            'montant_verse': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Montant à verser'
            }),
            'details_depenses': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2,
                'placeholder': 'Notes générales sur le versement...'
            }),
            'date_versement_reelle': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.superviseur = kwargs.pop('superviseur', None)
        super().__init__(*args, **kwargs)
        
        # Personnalisation des labels et help texts
        self.fields['type_versement'].help_text = (
            "Choisissez le type de versement. "
            "Les versements 'liés à la vente' impactent votre solde vente/recouvrement."
        )
        
        if self.superviseur:
            solde_vente = self.superviseur.solde_superviseur
            self.fields['type_versement'].help_text += f" - Solde disponible: {solde_vente} FCFA"
    
    def clean_date_versement_reelle(self):
        date_versement = self.cleaned_data.get('date_versement_reelle')
        if not date_versement:
            date_versement = timezone.now()
        return date_versement
    
    def clean(self):
        cleaned_data = super().clean()
        type_versement = cleaned_data.get('type_versement')
        montant_verse = cleaned_data.get('montant_verse')
        montant_depenses = cleaned_data.get('montant_depenses') or Decimal('0.00')
        
        # Validation pour les versements liés à la vente
        if type_versement == 'vente' and montant_verse and self.superviseur:
            # Créer une instance temporaire pour la validation
            versement_temp = VersementBancaire(
                superviseur=self.superviseur,
                type_versement=type_versement,
                montant_verse=montant_verse
            )
            
            # Calculer le montant net (versement - dépenses)
            montant_net = montant_verse - montant_depenses
            
            # Vérifier que le montant net ne dépasse pas le solde disponible
            solde_disponible = versement_temp.solde_disponible_vente_avant_versement
            if montant_net > solde_disponible:
                raise forms.ValidationError(
                    f"Le montant net du versement ({montant_net} FCFA) dépasse "
                    f"le solde disponible ({solde_disponible} FCFA) pour les ventes/recouvrements. "
                    f"Versement: {montant_verse} FCFA - Dépenses: {montant_depenses} FCFA"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Sauvegarde le versement et crée les dépenses associées"""
        versement = super().save(commit=False)
        versement.superviseur = self.superviseur
        
        if commit:
            versement.save()
            
            # Créer une dépense si un montant est spécifié
            montant_depenses = self.cleaned_data.get('montant_depenses')
            if montant_depenses and montant_depenses > 0:
                Depense.objects.create(
                    superviseur=self.superviseur,
                    versement=versement,
                    type_versement=versement.type_versement,
                    montant=montant_depenses,
                    description=self.cleaned_data.get('description_depenses', ''),
                    categorie=self.cleaned_data.get('categorie_depenses', 'autres'),
                    date_depense=self.cleaned_data.get('date_depenses') or timezone.now(),
                    justificatif=self.cleaned_data.get('justificatif_depenses')
                )
        
        return versement
    
    
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