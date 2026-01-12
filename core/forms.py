from django import forms
from datetime import datetime
from django.utils import timezone
from .models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,Dette,PaiementDette,
    DistributionAgent, Agent, DetailDistribution, FactureLotEntrepot,BonusAgent,
    MouvementStock,Recouvrement,VersementBancaire,Fournisseur,
    Depense,Perte,RecuVersement,PaiementFournisseur
)

from django.contrib.auth.models import User
from django.db import models
import os
from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField,Value
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



class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ['nom', 'contact', 'email', 'adresse']

class ReceptionLotForm(forms.ModelForm):
    """
    Formulaire de réception de lot
    - Le stock est TOUJOURS enregistré en kilogrammes
    - Le poids de référence est porté par le PRODUIT
    """

    # =============================
    # CHAMP UX UNIQUE
    # =============================
    quantite_saisie = forms.DecimalField(
        required=True,
        min_value=0.01,
        decimal_places=2,
        max_digits=10,
        label="Quantité reçue",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex : 20 (cartons) ou 50 (kg)'
        })
    )

    # =============================
    # PRODUIT (création)
    # =============================
    nouveau_produit = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Créer un nouveau produit"
    )

    nouveau_produit_nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Nom du produit"
    )

    nouveau_produit_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label="Description"
    )

    nouveau_produit_poids = forms.DecimalField(
        required=False,
        min_value=0.01,
        decimal_places=2,
        max_digits=10,
        label="Poids unitaire (kg)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex : 10 (laisser vide si non conditionné)'
        })
    )

    # =============================
    # FOURNISSEUR
    # =============================
    nouveau_fournisseur = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Créer un nouveau fournisseur"
    )

    nouveau_fournisseur_nom = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Nom du fournisseur"
    )

    nouveau_fournisseur_contact = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Contact"
    )

    # =============================
    # META
    # =============================
    class Meta:
        model = LotEntrepot
        fields = [
            'produit',
            'fournisseur',
            'quantite_initiale',  # champ technique
            'prix_achat_unitaire',
            'date_reception'
        ]
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'fournisseur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_initiale': forms.HiddenInput(),
            'prix_achat_unitaire': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_reception': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

    # =============================
    # INIT
    # =============================
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['produit'].queryset = Produit.objects.order_by('nom')
        self.fields['fournisseur'].queryset = Fournisseur.objects.order_by('nom')
        self.fields['quantite_initiale'].required = False
        self.fields['produit'].required = False
        self.fields['date_reception'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

    # =============================
    # CLEAN — LOGIQUE MÉTIER UNIQUE
    # =============================
    def clean(self):
        cleaned_data = super().clean()

        quantite_saisie = cleaned_data.get("quantite_saisie")
        nouveau_produit = cleaned_data.get("nouveau_produit")

        if not quantite_saisie or quantite_saisie <= 0:
            self.add_error("quantite_saisie", "La quantité doit être supérieure à 0")
            return cleaned_data

        # ---- CAS NOUVEAU PRODUIT ----
        if nouveau_produit:
            cleaned_data["produit"] = None
        
            nom = cleaned_data.get("nouveau_produit_nom")
            poids = cleaned_data.get("nouveau_produit_poids")
        
            if not nom:
                self.add_error("nouveau_produit_nom", "Nom du produit requis")
                return cleaned_data
        
            if quantite_saisie > 1 and not poids:
                self.add_error(
                    "nouveau_produit_poids",
                    "Le poids unitaire est requis pour un produit conditionné"
                )
                return cleaned_data
        
            if poids:
                cleaned_data["quantite_initiale"] = quantite_saisie * poids
            else:
                cleaned_data["quantite_initiale"] = quantite_saisie
        
            return cleaned_data
        

        # ---- PRODUIT EXISTANT ----
        produit = cleaned_data.get("produit")
        if not produit:
            self.add_error("produit", "Veuillez sélectionner un produit")
            return cleaned_data

        if produit.poids_unitaire_kg:
            cleaned_data["quantite_initiale"] = (
                quantite_saisie * produit.poids_unitaire_kg
            )
        else:
            cleaned_data["quantite_initiale"] = quantite_saisie

        return cleaned_data

    # =============================
    # SAVE
    # =============================
    def save(self, commit=True):
        instance = super().save(commit=False)

        # ----- Fournisseur -----
        if self.cleaned_data.get('nouveau_fournisseur'):
            fournisseur, _ = Fournisseur.objects.get_or_create(
                nom=self.cleaned_data['nouveau_fournisseur_nom'].strip(),
                defaults={'contact': self.cleaned_data.get('nouveau_fournisseur_contact', '')}
            )
            instance.fournisseur = fournisseur
        elif not self.cleaned_data.get('fournisseur'):
            instance.fournisseur, _ = Fournisseur.objects.get_or_create(
                nom="Fournisseur Inconnu",
                defaults={'contact': 'N/A'}
            )

        # ----- Produit -----
        if self.cleaned_data.get('nouveau_produit'):
            produit, created = Produit.objects.get_or_create(
                nom=self.cleaned_data['nouveau_produit_nom'].strip(),
                defaults={
                    'description': self.cleaned_data.get('nouveau_produit_description', ''),
                    'poids_unitaire_kg': self.cleaned_data.get('nouveau_produit_poids')
                }
            )

            if not created and self.cleaned_data.get('nouveau_produit_poids'):
                produit.poids_unitaire_kg = self.cleaned_data['nouveau_produit_poids']
                produit.save(update_fields=["poids_unitaire_kg"])

            instance.produit = produit

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

        # ----- Invariant métier -----
        instance.quantite_restante = instance.quantite_initiale

        if commit:
            instance.save()
            MouvementStock.objects.create(
                produit=instance.produit,
                lot=instance,
                type_mouvement='RECEPTION',
                quantite=instance.quantite_initiale,
                date_mouvement=instance.date_reception
            )

        return instance


import os
from django import forms
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


class FactureLotForm(forms.Form):
    fichiers = MultiFileField(
        required=True,
        widget=MultiFileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
        }),
        label="Factures",
        help_text="Sélectionnez un ou plusieurs fichiers (maintenez Ctrl pour sélection multiple)"
    )

    montants = forms.CharField(
        required=False,
        label="Montants associés (FCFA)",
        help_text="Ex: 100000,200000,150000 (un par fichier, optionnel)",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '100000,200000'
        })
    )

    description_generale = forms.CharField(
        required=False,
        label="Description commune",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Description pour toutes les factures'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        
        # Important: avec MultiFileField, les fichiers sont dans cleaned_data, pas dans self.files
        fichiers = cleaned_data.get('fichiers', [])
        montants_raw = cleaned_data.get('montants', '')
        
        # S'assurer que fichiers est une liste
        if not isinstance(fichiers, list):
            fichiers = [fichiers] if fichiers else []
        
        # Validation des fichiers
        if not fichiers:
            self.add_error('fichiers', 'Veuillez sélectionner au moins un fichier')
        else:
            # Vérifier chaque fichier
            for fichier in fichiers:
                if fichier:  # Vérifier que le fichier n'est pas None
                    # Vérifier la taille (max 10MB)
                    if fichier.size > 10 * 1024 * 1024:
                        self.add_error('fichiers', 
                            f'Le fichier "{fichier.name}" dépasse 10MB (taille: {fichier.size // (1024*1024)}MB)')
                    
                    # Vérifier l'extension
                    extensions_autorisees = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
                    extension = os.path.splitext(fichier.name)[1].lower()
                    if extension not in extensions_autorisees:
                        self.add_error('fichiers',
                            f'Type de fichier non autorisé pour "{fichier.name}". Formats acceptés: {", ".join(extensions_autorisees)}')
                else:
                    self.add_error('fichiers', 'Un ou plusieurs fichiers sont invalides')
        
        # Validation des montants
        if montants_raw:
            montants_list = [m.strip() for m in montants_raw.split(',') if m.strip()]
            
            # Vérifier que chaque montant est un nombre valide
            montants_valides = []
            for i, montant_str in enumerate(montants_list):
                try:
                    montant = Decimal(montant_str)
                    if montant <= 0:
                        self.add_error('montants', 
                            f'Le montant "{montant_str}" (position {i+1}) doit être positif')
                    else:
                        montants_valides.append(montant)
                except (InvalidOperation, ValueError):
                    self.add_error('montants', 
                        f'Montant invalide à la position {i+1}: "{montant_str}"')
            
            # Vérifier la correspondance avec le nombre de fichiers
            if fichiers and len(montants_valides) > len(fichiers):
                self.add_error('montants', 
                    f'Vous avez spécifié {len(montants_valides)} montants pour {len(fichiers)} fichier(s). '
                    f'Supprimez {len(montants_valides) - len(fichiers)} montant(s).')
            
            # Stocker les montants validés
            cleaned_data['montants_list'] = montants_valides
        else:
            cleaned_data['montants_list'] = []
        
        # Stocker le nombre de fichiers pour référence
        cleaned_data['nombre_fichiers'] = len(fichiers)
        
        return cleaned_data

    def save(self, lot):
        fichiers = self.cleaned_data.get('fichiers', [])
        description = self.cleaned_data.get('description_generale', '')
        montants_list = self.cleaned_data.get('montants_list', [])
        
        # S'assurer que fichiers est une liste
        if not isinstance(fichiers, list):
            fichiers = [fichiers] if fichiers else []
        
        factures = []
        for index, fichier in enumerate(fichiers):
            if fichier:  # Vérifier que le fichier n'est pas None
                # Attribuer un montant si disponible, sinon None
                montant = None
                if index < len(montants_list):
                    montant = montants_list[index]
                
                # Créer la facture
                facture = FactureLotEntrepot.objects.create(
                    lot=lot,
                    fichier=fichier,
                    montant=montant,
                    description=description
                )
                factures.append(facture)
        
        return factures
# core/forms.py


class PerteForm(forms.ModelForm):
    class Meta:
        model = Perte
        fields = ["quantite_perdue", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


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
    
  
# === FORMULAIRE VENTE ===

class VenteForm(forms.ModelForm):
    """
    Vente terrain :
    - uniquement produits distribués
    - prix imposé par le superviseur
    - détail + comptant uniquement
    """

    class Meta:
        model = Vente
        fields = [
            'detail_distribution',
            'quantite',
            'date_vente',
        ]
        widgets = {
            'detail_distribution': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.01',
                'step': '0.01'
            }),
            'date_vente': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent')
        super().__init__(*args, **kwargs)

        # Date par défaut
        self.fields['date_vente'].initial = timezone.now().strftime('%Y-%m-%dT%H:%M')

        # 🔒 PRODUITS DISPONIBLES UNIQUEMENT
        detail_qs = (
            DetailDistribution.objects
            .filter(distribution__agent_terrain=self.agent)
            .annotate(
                quantite_vendue_calculee=Coalesce(
                    Sum('vente__quantite'),
                    Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))
                ),
                quantite_restante=ExpressionWrapper(
                    F('quantite') - Coalesce(Sum('vente__quantite'), Value(0)),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
            .filter(quantite_restante__gt=0)
            .select_related('lot__produit', 'distribution')
        )

        self.fields['detail_distribution'].queryset = detail_qs
        self.fields['detail_distribution'].label_from_instance = self.label_distribution

    # ============================
    # AFFICHAGE
    # ============================

    def label_distribution(self, obj):
        return (
            f"{obj.lot.produit.nom} "
            f"(Stock: {obj.quantite_restante}) "
            f"- Prix: {obj.prix_detail} FCFA"
        )

    # ============================
    # VALIDATION
    # ============================

    def clean(self):
        cleaned_data = super().clean()
        detail = cleaned_data.get('detail_distribution')
        quantite = cleaned_data.get('quantite')

        if not detail:
            self.add_error('detail_distribution', "Produit requis")

        if not quantite or quantite <= 0:
            self.add_error('quantite', "Quantité invalide")

        if detail and quantite:
            # recalcul sécurité
            quantite_vendue = detail.vente_set.aggregate(
                total=Sum('quantite')
            )['total'] or 0

            quantite_disponible = detail.quantite - quantite_vendue

            if quantite > quantite_disponible:
                self.add_error(
                    'quantite',
                    f"Stock insuffisant. Disponible : {quantite_disponible}"
                )

        date_vente = cleaned_data.get('date_vente')
        if date_vente and date_vente > timezone.now():
            self.add_error('date_vente', "Date future interdite")

        return cleaned_data

    # ============================
    # SAUVEGARDE
    # ============================

    def save(self, commit=True):
        vente = super().save(commit=False)

        # 🔒 FORÇAGE MÉTIER
        vente.agent = self.agent
        vente.type_vente = 'detail'
        vente.mode_paiement = 'comptant'
        vente.stagiaire = None

        # 🔒 PRIX IMPOSÉ
        vente.prix_vente_unitaire = vente.detail_distribution.prix_detail

        if commit:
            vente.save()

        return vente

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
 

from decimal import Decimal
from django import forms
from django.db.models import Sum
from .models import PaiementFournisseur, LotEntrepot


class PaiementFournisseurForm(forms.ModelForm):

    class Meta:
        model = PaiementFournisseur
        fields = [
            'superviseur',
            'lot',
            'montant',
            'date_paiement',
        ]
        widgets = {
            'date_paiement': forms.DateInput(
                attrs={'type': 'date', 'class': 'input input-bordered w-full'}
            ),
            'montant': forms.NumberInput(
                attrs={'class': 'input input-bordered w-full'}
            ),
            'superviseur': forms.Select(
                attrs={'class': 'select select-bordered w-full'}
            ),
            'lot': forms.Select(
                attrs={'class': 'select select-bordered w-full'}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.fournisseur = kwargs.pop('fournisseur', None)
        super().__init__(*args, **kwargs)

        # 🔹 Filtrer les lots du fournisseur (logique direction)
        if self.fournisseur:
            self.fields['lot'].queryset = LotEntrepot.objects.filter(
                fournisseur=self.fournisseur
            ).order_by('-date_reception')

        # 🔹 UX dynamique : afficher le plafond réel
        lot = self._get_selected_lot()
        if lot:
            reste = self._get_reste_a_payer(lot)
            self.fields['montant'].widget.attrs.update({
                'max': reste,
                'placeholder': (
                    f"Max : {reste} FCFA "
                    f"(sur {lot.valeur_stock_initiale} FCFA)"
                )
            })

    # =========================
    # LOGIQUE MÉTIER
    # =========================

    def _get_selected_lot(self):
        if self.data.get('lot'):
            return LotEntrepot.objects.filter(id=self.data.get('lot')).first()
        if isinstance(self.initial.get('lot'), LotEntrepot):
            return self.initial.get('lot')
        return None

    def _get_total_paye(self, lot):
        return (
            PaiementFournisseur.objects.filter(
                lot=lot,
                est_supprime=False
            )
            .aggregate(total=Sum('montant'))['total']
            or Decimal('0.00')
        )

    def _get_reste_a_payer(self, lot):
        return max(
            lot.valeur_stock_initiale - self._get_total_paye(lot),
            Decimal('0.00')
        )

    # =========================
    # VALIDATION FINALE
    # =========================

    def clean(self):
        cleaned_data = super().clean()
        lot = cleaned_data.get('lot')
        montant = cleaned_data.get('montant')

        if not lot or not montant:
            return cleaned_data

        reste = self._get_reste_a_payer(lot)

        if montant <= 0:
            raise forms.ValidationError(
                "Le montant du paiement doit être strictement positif."
            )

        if montant > reste:
            raise forms.ValidationError(
                f"Paiement refusé : reste à payer {reste} FCFA "
                f"sur un total de {lot.valeur_stock_initiale} FCFA."
            )

        return cleaned_data
