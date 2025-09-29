from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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

    def __str__(self):
        return f"{self.nom} ({self.get_type_client_display()})"

class LotEntrepot(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.CASCADE)
    quantite_initiale = models.PositiveIntegerField()
    quantite_restante = models.PositiveIntegerField()
    prix_achat_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    date_reception = models.DateTimeField(default=timezone.now)
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

class Vente(models.Model):
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'terrain'}
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    detail_distribution = models.ForeignKey(DetailDistribution, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_vente_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    date_vente = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Vente {self.quantite} {self.detail_distribution.lot.produit.nom} à {self.client.nom}"

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