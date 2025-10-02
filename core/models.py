from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db import models



class Produit(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom

class Fournisseur(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    contact = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.nom

class Client(models.Model):
    TYPE_CLIENT_CHOICES = (
        ('grossiste', 'Grossiste'),
        ('detail', 'Détaillant'),
        ('particulier', 'Particulier'),
    )
    nom = models.CharField(max_length=100)
    contact = models.CharField(max_length=100, blank=True, null=True)
    type_client = models.CharField(max_length=20, choices=TYPE_CLIENT_CHOICES)
    date_creation = models.DateTimeField(default=timezone.now)  # Ajout de ce champ

    def __str__(self):
        return f"{self.nom} ({self.get_type_client_display()})"

    class Meta:
        ordering = ['nom'] 

class LotEntrepot(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE)
    quantite_initiale = models.PositiveIntegerField()
    quantite_restante = models.PositiveIntegerField()
    prix_achat_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    date_reception = models.DateTimeField(default=timezone.now)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    reference_lot = models.CharField(max_length=50, unique=True, blank=True, null=True)  # AJOUTEZ CE CHAMP

    def __str__(self):
        return f"{self.produit.nom} - {self.reference_lot} - {self.quantite_restante} restants"

    @staticmethod
    def get_lots_disponibles(produit_nom):
        return LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            quantite_restante__gt=0
        ).order_by("date_reception")

class Agent(models.Model):
    TYPE_AGENT_CHOICES = (
        ('entrepot', 'Superviseur (entrepôt)'),
        ('terrain', 'Agent terrain'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    type_agent = models.CharField(max_length=10, choices=TYPE_AGENT_CHOICES)
    telephone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_type_agent_display()}"

class DistributionAgent(models.Model):
    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="distributions_envoyees",
        limit_choices_to={'type_agent': 'entrepot'}
    )
    agent_terrain = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="distributions_recues",
        limit_choices_to={'type_agent': 'terrain'}
    )
    date_distribution = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Distribution {self.id} de {self.superviseur} → {self.agent_terrain}"

class DetailDistribution(models.Model):
    distribution = models.ForeignKey(DistributionAgent, on_delete=models.CASCADE)
    lot = models.ForeignKey(LotEntrepot, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()

    # Prix fixés par le superviseur
    prix_gros = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prix_detail = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.quantite} {self.lot.produit.nom} du lot {self.lot.id}"

class MouvementStock(models.Model):
    TYPE_MOUVEMENT = (
        ('RECEPTION', 'Réception fournisseur'),
        ('DISTRIBUTION', 'Distribution superviseur'),
        ('VENTE', 'Vente client'),
        ('RETOUR', 'Retour stock'),
    )
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    lot = models.ForeignKey(LotEntrepot, on_delete=models.CASCADE, null=True, blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, null=True, blank=True)
    type_mouvement = models.CharField(max_length=20, choices=TYPE_MOUVEMENT)
    quantite = models.PositiveIntegerField()
    date_mouvement = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.type_mouvement} - {self.produit.nom} ({self.quantite})"

class Facture(models.Model):

    TYPE_FACTURE_CHOICES = [
        ('entree', 'Facture Entrée - Entrepôt'),
        ('depot', 'Dépôt Agent - Superviseur'),
    ]
    
    type_facture = models.CharField(max_length=20, choices=TYPE_FACTURE_CHOICES)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='factures_deposees')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    fichier_facture = models.FileField(upload_to='factures_depots/')
    date_depot = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True)
    
    def __str__(self):
        type_str = "Entrepôt" if self.type_facture == 'entree' else "Dépôt Agent"
        return f"Facture {type_str} - {self.agent} - {self.montant} FCFA"
    
    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"


class Vente(models.Model):
    TYPE_VENTE_CHOICES = (
        ('gros', 'Vente en Gros'),
        ('detail', 'Vente au Détail'),
    )
    
    MODE_PAIEMENT_CHOICES = (
        ('comptant', 'Paiement Comptant'),
        ('credit', 'Paiement à Crédit'),
    )
    
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'terrain'}
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    detail_distribution = models.ForeignKey(DetailDistribution, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    type_vente = models.CharField(max_length=10, choices=TYPE_VENTE_CHOICES, default='detail')
    prix_vente_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, default='comptant')
    date_vente = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Déterminer automatiquement le prix en fonction du type de vente choisi
        if not self.prix_vente_unitaire:
            if self.type_vente == 'gros':
                self.prix_vente_unitaire = self.detail_distribution.prix_gros
            else:
                self.prix_vente_unitaire = self.detail_distribution.prix_detail
        
        super().save(*args, **kwargs)
        
        # Créer automatiquement une dette si c'est un paiement à crédit
        if self.mode_paiement == 'credit' and not hasattr(self, 'dette'):
            Dette.objects.create(
                vente=self,
                montant_total=self.total_vente,
                montant_restant=self.total_vente,
                date_echeance=timezone.now().date() + timedelta(days=30)
            )

    @property
    def produit_nom(self):
        return self.detail_distribution.lot.produit.nom

    @property
    def total_vente(self):
        return self.quantite * self.prix_vente_unitaire

    def get_type_vente_display(self):
        return "Gros" if self.type_vente == 'gros' else "Détail"
    
    @property
    def est_credit(self):
        return self.mode_paiement == 'credit'
    
    @property
    def dette_associee(self):
        if hasattr(self, 'dette'):
            return self.dette
        return None

class Dette(models.Model):
    STATUT_CHOICES = (
        ('en_cours', 'En cours'),
        ('partiellement_paye', 'Partiellement payé'),
        ('paye', 'Payé'),
        ('en_retard', 'En retard'),
    )
    
    vente = models.OneToOneField(
        'Vente', 
        on_delete=models.CASCADE,
        related_name='dette'
    )
    montant_total = models.DecimalField(max_digits=10, decimal_places=2)
    montant_restant = models.DecimalField(max_digits=10, decimal_places=2)
    date_creation = models.DateTimeField(default=timezone.now)
    date_echeance = models.DateField()
    date_reglement = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_cours')
    
    # Informations de localisation détaillées
    nom_localite = models.CharField(max_length=100, blank=True)
    
    # Bonus pour recouvrement rapide
    bonus_accorde = models.BooleanField(default=False)
    nombre_produits_bonus = models.PositiveIntegerField(default=0)  # Nombre de produits pour le bonus
    delai_bonus_heures = models.PositiveIntegerField(default=48)  # 48h = 2 jours par défaut
    
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Dette {self.montant_restant}€ - {self.vente.client.nom} - {self.nom_localite}"
    
    @property
    def delai_bonus_expire(self):
        """Vérifie si le délai pour le bonus est expiré"""
        delai_bonus = timedelta(hours=self.delai_bonus_heures)
        return timezone.now() > self.date_creation + delai_bonus
    
    @property
    def temps_restant_bonus(self):
        """Retourne le temps restant pour bénéficier du bonus"""
        if self.bonus_accorde or self.statut == 'paye':
            return None
        
        delai_bonus = timedelta(hours=self.delai_bonus_heures)
        date_limite = self.date_creation + delai_bonus
        temps_restant = date_limite - timezone.now()
        
        return max(temps_restant, timedelta(0))
    
    @property
    def eligible_bonus(self):
        """Vérifie si la dette est éligible au bonus"""
        return (not self.bonus_accorde and 
                not self.delai_bonus_expire and 
                self.statut != 'paye')
    
    def accorder_bonus(self):
        """Accorde le bonus basé sur le nombre de produits dans la vente"""
        if self.eligible_bonus and not self.bonus_accorde:
            self.bonus_accorde = True
            self.nombre_produits_bonus = self.vente.quantite
            
            # Mettre à jour le bonus de l'agent
            agent_bonus, created = BonusAgent.objects.get_or_create(
                agent=self.vente.agent,
                defaults={'nombre_produits_recouverts': 0, 'total_bonus': 0}
            )
            agent_bonus.ajouter_produits_recouverts(self.vente.quantite)
            
            self.save()
            return self.vente.quantite  # Retourne le nombre de produits
        return 0
    
    def save(self, *args, **kwargs):
        # Mettre à jour automatiquement le statut
        if self.montant_restant <= 0:
            ancien_statut = self.statut
            self.statut = 'paye'
            self.date_reglement = timezone.now().date()
            
            # Accorder automatiquement le bonus si payé dans les délais
            if self.eligible_bonus and ancien_statut != 'paye':
                self.accorder_bonus()
                
        elif self.montant_restant < self.montant_total:
            self.statut = 'partiellement_paye'
        elif self.date_echeance < timezone.now().date():
            self.statut = 'en_retard'
        else:
            self.statut = 'en_cours'
            
        super().save(*args, **kwargs)
    
    @property
    def montant_bonus(self):
        """Calcule le montant du bonus pour cette dette"""
        return self.nombre_produits_bonus * 100


class PaiementDette(models.Model):
    MODE_PAIEMENT_CHOICES = (
        ('espece', 'Espèce'),
        ('cheque', 'Chèque'),
        ('virement', 'Virement'),
        ('mobile', 'Paiement Mobile'),
    )
    
    dette = models.ForeignKey(
        Dette, 
        on_delete=models.CASCADE, 
        related_name='paiements'
    )
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateTimeField(default=timezone.now)
    mode_paiement = models.CharField(max_length=10, choices=MODE_PAIEMENT_CHOICES, default='espece')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    # Suivi du bonus
    bonus_genere = models.BooleanField(default=False)
    nombre_produits_bonus = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"Paiement {self.montant}€ - {self.dette.vente.client.nom}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Mettre à jour le montant restant de la dette
        if is_new:
            ancien_montant_restant = self.dette.montant_restant
            self.dette.montant_restant -= self.montant
            
            # Vérifier si le paiement règle complètement la dette
            if self.dette.montant_restant <= 0 and ancien_montant_restant > 0:
                # Accorder le bonus si éligible
                if self.dette.eligible_bonus:
                    nombre_produits = self.dette.accorder_bonus()
                    self.bonus_genere = True
                    self.nombre_produits_bonus = nombre_produits
                    super().save(update_fields=['bonus_genere', 'nombre_produits_bonus'])
            
            self.dette.save()


class BonusAgent(models.Model):
    agent = models.OneToOneField(
        Agent,
        on_delete=models.CASCADE,
        related_name='bonus'
    )
    nombre_produits_recouverts = models.PositiveIntegerField(default=0)
    total_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Bonus {self.nombre_produits_recouverts} produits - {self.agent.nom}"
    
    def calculer_bonus_total(self):
        """Calcule le bonus total: 100 F par produit recouvert à temps"""
        bonus_par_produit = 100  # 100 FCFA par produit recouvert à temps
        self.total_bonus = self.nombre_produits_recouverts * bonus_par_produit
        return self.total_bonus
    
    def ajouter_produits_recouverts(self, nombre_produits):
        """Ajoute un nombre de produits recouverts à temps"""
        self.nombre_produits_recouverts += nombre_produits
        self.calculer_bonus_total()
        self.save()
    
    @property
    def dettes_avec_bonus(self):
        """Retourne les dettes pour lesquelles l'agent a obtenu un bonus"""
        return Dette.objects.filter(
            vente__agent=self.agent,
            bonus_accorde=True
        )
    
    def get_produits_recouverts_par_mois(self, mois=None, annee=None):
        """Retourne le nombre de produits recouverts par mois"""
        if mois is None:
            mois = timezone.now().month
        if annee is None:
            annee = timezone.now().year
            
        dettes_bonus = Dette.objects.filter(
            vente__agent=self.agent,
            bonus_accorde=True,
            date_reglement__month=mois,
            date_reglement__year=annee
        )
        
        total_produits = 0
        for dette in dettes_bonus:
            total_produits += dette.vente.quantite
            
        return total_produits
