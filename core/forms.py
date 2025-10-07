from django import forms
from datetime import datetime
from django.utils import timezone
from .models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,Dette,PaiementDette,
    DistributionAgent, Agent, DetailDistribution, Facture,BonusAgent,
    MouvementStock,Recouvrement
)
from django.db import models

import os

# forms.py
# forms.py
import os
from django import forms
from django.utils import timezone
from datetime import datetime
from .models import LotEntrepot, Produit, Fournisseur, MouvementStock

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
                'min': '1',
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
            if not cleaned_data.get('fournisseur'):
                self.add_error('fournisseur', 'Veuillez sélectionner un fournisseur existant')
        
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
        self.fields['agent_terrain'].queryset = Agent.objects.filter(type_agent='terrain')
        self.fields['agent_terrain'].empty_label = "Sélectionner un agent terrain"
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
        
        # Validation selon le type de distribution
        if type_distribution == 'TERRAIN':
            if not cleaned_data.get('agent_terrain'):
                self.add_error('agent_terrain', 'Agent terrain requis pour une distribution terrain')
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
        Calcule le stock disponible à une date donnée en tenant compte
        des distributions antérieures à cette date
        """
        from django.db.models import Sum
        
        # Stock initial (lots reçus avant la date de référence)
        lots_initial = LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            date_reception__lte=date_reference
        )
        
        stock_total = sum(lot.quantite_initiale for lot in lots_initial)
        
        # Soustraire les distributions antérieures à cette date
        distributions_anterieures = DetailDistribution.objects.filter(
            distribution__date_distribution__lte=date_reference,
            lot__produit__nom=produit_nom
        )
        
        quantite_distribuee = distributions_anterieures.aggregate(
            total=Sum('quantite')
        )['total'] or 0
        
        return stock_total - quantite_distribuee

    def get_lots_disponibles_a_date(self, produit_nom, date_reference):
        """Retourne les lots disponibles à une date donnée en VRAI FIFO"""
        from django.db.models import Sum
    
        lots = LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            date_reception__lte=date_reference
        ).order_by('date_reception')  # FIFO = plus ancienne date d'abord
    
        lots_avec_stock = []
        for lot in lots:
            quantite_distribuee = DetailDistribution.objects.filter(
                lot=lot,
                distribution__date_distribution__lte=date_reference
            ).aggregate(total=Sum('quantite'))['total'] or 0
    
            quantite_restante = lot.quantite_initiale - quantite_distribuee
    
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

                            # Préparer les objets à créer
                            details_creation.append(DetailDistribution(
                                distribution=instance,
                                lot=lot,
                                quantite=quantite_a_prelever,
                                prix_gros=self.cleaned_data.get('prix_gros'),
                                prix_detail=self.cleaned_data.get('prix_detail')
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
class VenteForm(forms.ModelForm):
    # Nouveau client
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
            'placeholder': 'Nom du client'
        })
    )
    client_contact = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Contact (téléphone)'
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

    class Meta:
        model = Vente
        fields = ['client', 'detail_distribution', 'quantite', 'type_vente', 'mode_paiement', 'prix_vente_unitaire']
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
        self.fields['client'].required = False
        self.fields['detail_distribution'].required = False
        self.fields['quantite'].required = False
        self.fields['type_vente'].required = True
        self.fields['mode_paiement'].required = True
        self.fields['prix_vente_unitaire'].required = False
        
        # Filtrer les clients existants
        self.fields['client'].queryset = Client.objects.all()
        self.fields['client'].empty_label = "Sélectionner un client existant..."
        
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

        # Initialiser les champs nouveau client comme désactivés
        self.fields['client_nom'].widget.attrs['disabled'] = True
        self.fields['client_contact'].widget.attrs['disabled'] = True
        self.fields['client_type'].widget.attrs['disabled'] = True

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation client
        if cleaned_data.get('nouveau_client'):
            if not cleaned_data.get('client_nom'):
                self.add_error('client_nom', 'Nom requis pour un nouveau client')
        else:
            if not cleaned_data.get('client'):
                self.add_error('client', 'Veuillez sélectionner un client existant')
                
        # Validation de base
        if not cleaned_data.get('detail_distribution'):
            self.add_error('detail_distribution', 'Produit à vendre requis')
        
        if not cleaned_data.get('quantite') or cleaned_data.get('quantite', 0) <= 0:
            self.add_error('quantite', 'Quantité valide requise')
        
        # Vérifier la quantité disponible
        if cleaned_data.get('detail_distribution') and cleaned_data.get('quantite'):
            detail = cleaned_data['detail_distribution']
            if cleaned_data['quantite'] > detail.quantite:
                self.add_error('quantite', f'Quantité insuffisante. Disponible: {detail.quantite}')
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Associer l'agent
        instance.agent = self.agent

        # Si nouveau client → créer et l'associer
        if self.cleaned_data.get('nouveau_client'):
            client = Client.objects.create(
                nom=self.cleaned_data['client_nom'],
                contact=self.cleaned_data.get('client_contact', ''),
                type_client=self.cleaned_data.get('client_type', 'detail')
            )
            instance.client = client

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
        
class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = ['type_facture', 'montant', 'fichier_facture', 'description'] 
        widgets = {
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fichier_facture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

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