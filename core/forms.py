from django import forms
from datetime import datetime
from .models import (
    Vente, Produit, Client, LotEntrepot, Fournisseur,
    DistributionAgent, Agent, DetailDistribution, Facture
)

# forms.py
class ReceptionLotForm(forms.ModelForm):
    # Champs pour nouveau fournisseur
    nouveau_fournisseur = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    nouveau_fournisseur_nom = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du fournisseur',
            'disabled': True
        })
    )
    nouveau_fournisseur_contact = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Contact',
            'disabled': True
        })
    )
    
    # Champs pour nouveau produit
    nouveau_produit = forms.BooleanField(
        required=False, 
        initial=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    nouveau_produit_nom = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Nom du produit',
            'disabled': True
        })
    )
    nouveau_produit_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'placeholder': 'Description (optionnel)',
            'rows': 2,
            'disabled': True
        })
    )

    class Meta:
        model = LotEntrepot
        fields = ['produit', 'fournisseur', 'quantite_initiale', 'prix_achat_unitaire']
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'fournisseur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_initiale': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'prix_achat_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre tous les champs non obligatoires
        self.fields['produit'].required = False
        self.fields['fournisseur'].required = False
        self.fields['quantite_initiale'].required = False
        self.fields['prix_achat_unitaire'].required = False
        
        # Peupler les listes déroulantes
        self.fields['produit'].queryset = Produit.objects.all()
        self.fields['produit'].empty_label = "Sélectionner un produit..."
        self.fields['fournisseur'].queryset = Fournisseur.objects.all()
        self.fields['fournisseur'].empty_label = "Sélectionner un fournisseur..."

    def clean(self):
        cleaned_data = super().clean()
        nouveau_fournisseur = cleaned_data.get('nouveau_fournisseur')
        nouveau_produit = cleaned_data.get('nouveau_produit')
        
        # Validation fournisseur
        if nouveau_fournisseur:
            if not cleaned_data.get('nouveau_fournisseur_nom'):
                self.add_error('nouveau_fournisseur_nom', 'Nom du fournisseur requis')
            elif Fournisseur.objects.filter(nom=cleaned_data['nouveau_fournisseur_nom']).exists():
                self.add_error('nouveau_fournisseur_nom', 'Ce fournisseur existe déjà')
        else:
            if not cleaned_data.get('fournisseur'):
                self.add_error('fournisseur', 'Veuillez sélectionner un fournisseur existant')
        
        # Validation produit
        if nouveau_produit:
            if not cleaned_data.get('nouveau_produit_nom'):
                self.add_error('nouveau_produit_nom', 'Nom du produit requis')
            elif Produit.objects.filter(nom=cleaned_data['nouveau_produit_nom']).exists():
                self.add_error('nouveau_produit_nom', 'Ce produit existe déjà')
        else:
            if not cleaned_data.get('produit'):
                self.add_error('produit', 'Veuillez sélectionner un produit existant')
        
        # Validation de base
        if not cleaned_data.get('quantite_initiale') or cleaned_data.get('quantite_initiale', 0) <= 0:
            self.add_error('quantite_initiale', 'Quantité valide requise')
        if not cleaned_data.get('prix_achat_unitaire') or cleaned_data.get('prix_achat_unitaire', 0) <= 0:
            self.add_error('prix_achat_unitaire', 'Prix d\'achat valide requis')
            
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Gérer le fournisseur
        if self.cleaned_data.get('nouveau_fournisseur'):
            fournisseur = Fournisseur.objects.create(
                nom=self.cleaned_data['nouveau_fournisseur_nom'],
                contact=self.cleaned_data.get('nouveau_fournisseur_contact', '')
            )
            instance.fournisseur = fournisseur

        # Gérer le produit
        if self.cleaned_data.get('nouveau_produit'):
            produit = Produit.objects.create(
                nom=self.cleaned_data['nouveau_produit_nom'],
                description=self.cleaned_data.get('nouveau_produit_description', '')
            )
            instance.produit = produit

        # Générer une référence de lot
        if not instance.reference_lot:
            prefix = datetime.now().strftime("%Y%m%d")
            dernier_lot = LotEntrepot.objects.filter(
                reference_lot__startswith=prefix
            ).order_by('-reference_lot').first()
            
            if dernier_lot:
                try:
                    dernier_num = int(dernier_lot.reference_lot[-4:])
                    nouveau_num = dernier_num + 1
                except ValueError:
                    nouveau_num = 1
            else:
                nouveau_num = 1
                
            instance.reference_lot = f"{prefix}-{nouveau_num:04d}"

        # Initialiser la quantité restante
        instance.quantite_restante = instance.quantite_initiale

        if commit:
            instance.save()
        return instance

# forms.py
class DistributionForm(forms.ModelForm):
    # Champs dynamiques pour les produits
    produit = forms.ModelChoiceField(
        queryset=Produit.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantite = forms.IntegerField(
        min_value=1,
        required=False,
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

    class Meta:
        model = DistributionAgent
        fields = ['agent_terrain']
        widgets = {
            'agent_terrain': forms.Select(attrs={'class': 'form-select', 'id': 'agent-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        
        # Limiter aux agents terrain
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

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation de base
        if not cleaned_data.get('agent_terrain'):
            self.add_error('agent_terrain', 'Agent terrain requis')
        if not cleaned_data.get('produit'):
            self.add_error('produit', 'Produit requis')
        if not cleaned_data.get('quantite') or cleaned_data.get('quantite', 0) <= 0:
            self.add_error('quantite', 'Quantité valide requise')
        
        # Vérifier le stock disponible
        if cleaned_data.get('produit') and cleaned_data.get('quantite'):
            produit_nom = cleaned_data['produit'].nom
            quantite_demandee = cleaned_data['quantite']
            lots_disponibles = LotEntrepot.get_lots_disponibles(produit_nom)
            stock_total = sum(lot.quantite_restante for lot in lots_disponibles)
            
            if quantite_demandee > stock_total:
                self.add_error('quantite', f'Stock insuffisant. Disponible: {stock_total} unités')
            
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Définir le superviseur automatiquement (l'utilisateur connecté)
        try:
            superviseur = Agent.objects.get(user=self.current_user, type_agent='entrepot')
            instance.superviseur = superviseur
        except Agent.DoesNotExist:
            # Créer un superviseur si nécessaire
            superviseur = Agent.objects.create(
                user=self.current_user,
                type_agent='entrepot'
            )
            instance.superviseur = superviseur

        if commit:
            instance.save()
            
            # Créer le détail de distribution
            if (self.cleaned_data.get('produit') and 
                self.cleaned_data.get('quantite')):
                
                # Trouver un lot disponible (FIFO)
                produit_nom = self.cleaned_data['produit'].nom
                quantite_demandee = self.cleaned_data['quantite']
                lots_disponibles = LotEntrepot.get_lots_disponibles(produit_nom)
                
                quantite_restante = quantite_demandee
                for lot in lots_disponibles:
                    if quantite_restante <= 0:
                        break
                    
                    quantite_a_prelever = min(quantite_restante, lot.quantite_restante)
                    
                    DetailDistribution.objects.create(
                        distribution=instance,
                        lot=lot,
                        quantite=quantite_a_prelever,
                        prix_gros=self.cleaned_data.get('prix_gros'),
                        prix_detail=self.cleaned_data.get('prix_detail')
                    )
                    
                    # Mettre à jour le stock du lot
                    lot.quantite_restante -= quantite_a_prelever
                    lot.save()
                    
                    quantite_restante -= quantite_a_prelever
                
                if quantite_restante > 0:
                    raise forms.ValidationError(f"Stock insuffisant pour {produit_nom}. Manquant: {quantite_restante}")
        
        return instance

# === FORMULAIRE VENTE ===
# forms.py
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
            'placeholder': 'Nom du client',
            'disabled': True
        })
    )
    client_contact = forms.CharField(
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Contact (téléphone)',
            'disabled': True
        })
    )
    client_type = forms.ChoiceField(
        choices=Client.TYPE_CLIENT_CHOICES,
        required=False,
        initial='detail',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'disabled': True
        })
    )

    class Meta:
        model = Vente
        fields = ['client', 'detail_distribution', 'quantite', 'prix_vente_unitaire']
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'detail_distribution': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'quantite-vente'}),
            'prix_vente_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'prix-vente'}),
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        # Rendre tous les champs non obligatoires
        self.fields['client'].required = False
        self.fields['detail_distribution'].required = False
        self.fields['quantite'].required = False
        self.fields['prix_vente_unitaire'].required = False
        
        # Filtrer les clients existants
        self.fields['client'].queryset = Client.objects.all()
        self.fields['client'].empty_label = "Sélectionner un client existant..."
        
        # Filtrer les détails de distribution disponibles pour cet agent
        if self.agent:
            self.fields['detail_distribution'].queryset = DetailDistribution.objects.filter(
                distribution__agent_terrain=self.agent
            ).select_related('lot', 'lot__produit')
            
            # Ajouter des informations utiles dans l'affichage
            self.fields['detail_distribution'].label_from_instance = lambda obj: (
                f"{obj.lot.produit.nom} - Lot {obj.lot.reference_lot} - "
                f"Disponible: {obj.quantite} - "
                f"Prix gros: {obj.prix_gros or 'N/D'} - "
                f"Prix détail: {obj.prix_detail or 'N/D'}"
            )

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
        
        if not cleaned_data.get('prix_vente_unitaire') or cleaned_data.get('prix_vente_unitaire', 0) <= 0:
            self.add_error('prix_vente_unitaire', 'Prix de vente valide requis')
        
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

        if commit:
            instance.save()
            
            # Mettre à jour la quantité restante dans le détail de distribution
            detail = instance.detail_distribution
            detail.quantite -= instance.quantite
            detail.save()
            
        return instance

# === FORMULAIRE FACTURE/VERSEMENT ===
class FactureForm(forms.ModelForm):
    class Meta:
        model = Facture
        fields = ['type_facture', 'montant', 'fichier_facture', 'description']
        widgets = {
            'type_facture': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fichier_facture': forms.FileInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.agent = kwargs.pop('agent', None)
        super().__init__(*args, **kwargs)
        
        # Rendre tous les champs non obligatoires
        self.fields['type_facture'].required = False
        self.fields['montant'].required = False
        self.fields['fichier_facture'].required = False
        self.fields['description'].required = False

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation de base
        if not cleaned_data.get('montant') or cleaned_data.get('montant', 0) <= 0:
            self.add_error('montant', 'Montant valide requis')
            
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Associer l'agent automatiquement
        instance.agent = self.agent

        if commit:
            instance.save()
        return instance