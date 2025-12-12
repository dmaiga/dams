from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from tinymce.models import HTMLField
from datetime import timedelta

from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
)
from django.db.models.functions import Coalesce
from django.core.validators import MinValueValidator
from decimal import Decimal


class Client(models.Model):
    TYPE_CLIENT_CHOICES = (
        ('grossiste', 'Grossiste'),
        ('detail', 'Détaillant'),
        ('particulier', 'Particulier'),
    )
    nom = models.CharField(max_length=100)
    contact = models.CharField(max_length=100, blank=True, null=True)
    type_client = models.CharField(max_length=50, choices=TYPE_CLIENT_CHOICES)
    date_creation = models.DateTimeField(default=timezone.now)  # Ajout de ce champ

    def __str__(self):
        return f"{self.nom} ({self.get_type_client_display()})"

    class Meta:
        ordering = ['nom'] 

class Produit(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom

class Fournisseur(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    contact = models.CharField(max_length=100, blank=True, null=True)
    adresse = models.CharField(max_length=200, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def get_dette_actuelle(self, date_debut=None, date_fin=None):
        """Dette actuelle du fournisseur (produits écoulés seulement)"""
        from .services.fournisseur_service import FournisseurAnalyseService
        return FournisseurAnalyseService.get_dette_fournisseur(self.id, date_debut, date_fin)
    
    def get_stats_periode(self, date_debut=None, date_fin=None):
        """Statistiques du fournisseur pour une période"""
        from .services.fournisseur_service import FournisseurAnalyseService
        return FournisseurAnalyseService.get_detail_fournisseur(self.id, date_debut, date_fin)
    
    @property
    def nombre_lots_actifs(self):
        """Nombre de lots actifs (avec stock restant)"""
        return self.lotentrepot_set.filter(quantite_restante__gt=0).count()
    
    @property
    def valeur_stock_total(self):
        """Valeur totale du stock actuel"""
        from django.db.models import Sum
        result = self.lotentrepot_set.aggregate(
            total=Sum(F('quantite_restante') * F('prix_achat_unitaire'))
        )
        return result['total'] or Decimal('0.00')
    
    def __str__(self):
        return self.nom

    class Meta:
        ordering = ['nom']

class LotEntrepot(models.Model):
    produit = models.ForeignKey(Produit,
                                 on_delete=models.CASCADE,
                                 related_name="lots")
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        verbose_name="Fournisseur (optionnel)"
    )
    quantite_initiale = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_restante = models.DecimalField(max_digits=10, decimal_places=2)
    prix_achat_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    valeur_stock_initiale = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )
    date_reception = models.DateTimeField(default=timezone.now)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    reference_lot = models.CharField(max_length=100, unique=True, blank=True, null=True) 
    facture = models.FileField(
        upload_to='factures_entrepot/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Facture (optionnel)"
    )
    date_upload_facture = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Date d'upload de la facture"
    )

    def __str__(self):
        return f"{self.produit.nom} - {self.fournisseur} - {self.quantite_restante} restants"
    
    def save(self, *args, **kwargs):
        # Si la valeur initiale n'est pas encore enregistrée, on la calcule UNE SEULE FOIS
        if self.valeur_stock_initiale is None:
            self.valeur_stock_initiale = self.quantite_initiale * (self.prix_achat_unitaire or 0)
        
        # Validation de cohérence des quantités
        if self.quantite_restante > self.quantite_initiale:
            raise ValueError("La quantité restante ne peut pas être supérieure à la quantité initiale")
        
        if self.quantite_restante < 0:
            raise ValueError("La quantité restante ne peut pas être négative")

        super().save(*args, **kwargs)
    
    @property
    def montant_total(self):
        """Calcule le montant total du lot"""
        return self.quantite_initiale * (self.prix_achat_unitaire or 0)
    
    @property
    def valeur_actuelle_stock(self):
        """Calcule la valeur actuelle du stock basée sur la quantité restante"""
        return self.quantite_restante * (self.prix_achat_unitaire or 0)
    
    @property
    def quantite_perdue_totale(self):
        """Calcule la quantité totale perdue pour ce lot"""
        return sum(perte.quantite_perdue for perte in self.pertes.all())
    
    @property
    def quantite_theorique_restante(self):
        """Quantité théorique restante (initiale - pertes)"""
        return self.quantite_initiale - self.quantite_perdue_totale
    
    @property
    def coherence_quantites(self):
        """Vérifie la cohérence entre quantité restante et pertes"""
        return self.quantite_restante == self.quantite_theorique_restante
    
    @property
    def ecart_quantite(self):
        """Retourne l'écart entre quantité réelle et théorique"""
        return self.quantite_restante - self.quantite_theorique_restante
    
    def recalculer_quantite_restante(self):
        """Recalcule la quantité restante basée sur les pertes"""
        self.quantite_restante = self.quantite_theorique_restante
        self.save()
    
    @staticmethod
    def get_lots_disponibles(produit_nom):
        return LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            quantite_restante__gt=0
        ).order_by("date_reception")
    
# core/models.py
class Perte(models.Model):
    lot = models.ForeignKey(
        LotEntrepot,
        on_delete=models.CASCADE,
        related_name="pertes"
    )
    quantite_perdue = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_perdue_originale = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Quantité perdue initiale"
    )
    description = models.TextField()
    date_perte = models.DateTimeField(default=timezone.now)
    date_modification = models.DateTimeField(auto_now=True)
    est_modifiee = models.BooleanField(default=False)
    
    def __str__(self):
        statut = " (modifiée)" if self.est_modifiee else ""
        return f"Perte de {self.quantite_perdue} sur {self.lot}{statut}"
    
    def save(self, *args, **kwargs):
        from django.db import transaction
        
        with transaction.atomic():
            if not self.pk:  # Création
                # Sauvegarder la quantité originale
                self.quantite_perdue_originale = self.quantite_perdue
                # Déduire la quantité du lot
                self.lot.quantite_restante -= self.quantite_perdue
                self.lot.save()
            else:  # Modification
                ancienne_perte = Perte.objects.get(pk=self.pk)
                difference = self.quantite_perdue - ancienne_perte.quantite_perdue
                
                if difference != 0:
                    # Ajuster la quantité du lot
                    self.lot.quantite_restante -= difference
                    self.lot.save()
                    self.est_modifiee = True
            
            super().save(*args, **kwargs)
    
    def delete(self, using=None, keep_parents=False):
        """Restituer la quantité au lot lors de la suppression"""
        from django.db import transaction
        
        with transaction.atomic():
            # Restituer la quantité perdue au lot
            self.lot.quantite_restante += self.quantite_perdue
            self.lot.save()
            super().delete(using=using, keep_parents=keep_parents)
    
    @property
    def difference_quantite(self):
        """Retourne la différence entre la quantité actuelle et originale"""
        return self.quantite_perdue - self.quantite_perdue_originale
    
    @property
    def impact_quantite(self):
        """Retourne l'impact sur la quantité du lot"""
        return {
            'quantite_avant_perte': self.lot.quantite_initiale,
            'quantite_actuelle': self.lot.quantite_restante,
            'quantite_perdue_totale': self.quantite_perdue,
            'quantite_originale': self.quantite_perdue_originale,
            'difference': self.difference_quantite
        }
    


class Agent(models.Model):
    TYPE_AGENT_CHOICES = (
        ('direction', 'Direction'),
        ('entrepot', 'Superviseur'),
        ('terrain', 'Agent'),
        ('stagiaire', 'Stagiaire'), 
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    type_agent = models.CharField(max_length=50, choices=TYPE_AGENT_CHOICES)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    ajustement_solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Ajustement manuel du solde (+/- FCFA)"
    )

    # 🕒 champs pour la gestion automatique de l’expiration
    date_creation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(
    "Date d’expiration (stagiaire)",
    blank=True, null=True
    )
    date_mise_service = models.DateTimeField(
        "Date de mise en service",
        blank=True, null=True,
        help_text="Date à laquelle le stagiaire a commencé son activité"
    )
   
    def save(self, *args, **kwargs):
        # 🔹 Si c’est un stagiaire nouvellement créé, on fixe la date d’expiration
       
        if self.type_agent == 'stagiaire':
            if not self.date_mise_service:
                self.date_mise_service = timezone.now()
            
            #  Calculer l'expiration à partir de la date de mise en service
            if not self.date_expiration:
                self.date_expiration = self.date_mise_service + timedelta(days=14)

        # 🔹 Si l’agent change de rôle (n’est plus stagiaire)
        elif self.type_agent != 'stagiaire':
            # On réactive le compte au besoin
            if not self.user.is_active:
                self.user.is_active = True
                self.user.save(update_fields=['is_active'])
            # On efface les dates spécifiques stagiaire
            self.date_expiration = None
            self.date_mise_service = None

        super().save(*args, **kwargs)

    def get_stats_ventes_periode(self, jours=30):
        """Retourne les statistiques de vente pour une période donnée"""
        date_debut = timezone.now() - timedelta(days=jours)
        ventes = Vente.objects.filter(agent=self, date_vente__gte=date_debut)
        
        stats = ventes.aggregate(
            total_ventes=Sum(F('quantite') * F('prix_vente_unitaire')),
            nombre_ventes=Count('id'),
            quantite_vendue=Sum('quantite')
        )
        
        # Stats par type de vente
        ventes_gros = ventes.filter(type_vente='gros')
        ventes_detail = ventes.filter(type_vente='detail')
        
        stats_gros = ventes_gros.aggregate(
            total=Sum(F('quantite') * F('prix_vente_unitaire')),
            quantite=Sum('quantite'),
            nombre=Count('id')
        )
        
        stats_detail = ventes_detail.aggregate(
            total=Sum(F('quantite') * F('prix_vente_unitaire')),
            quantite=Sum('quantite'),
            nombre=Count('id')
        )
        
        return {
            'general': stats,
            'gros': stats_gros,
            'detail': stats_detail,
            'periode_jours': jours
        }


    def __str__(self):
        return f"{self.full_name} - {self.get_type_agent_display()}"

    @property
    def est_expire(self):
        """Vérifie si le stagiaire a dépassé sa date d’expiration"""
        if self.type_agent == 'stagiaire' and self.date_expiration:
            return timezone.now() > self.date_expiration
        return False

    @property
    def a_acces_plateforme(self):
        """Renvoie True si l'agent a droit d'accéder à la plateforme"""
        if self.type_agent == 'stagiaire':
            return not self.est_expire
        return True
    

    @property
    def est_stagiaire(self):
        """Vérifie si l'agent est un stagiaire"""
        return self.type_agent == 'stagiaire'

    @property
    def statut_stagiaire(self):
        """Retourne le statut du stagiaire"""
        if not self.est_stagiaire:
            return "Non applicable"
        if self.est_expire:
            return "Expiré"
        return f"Valide ({self.jours_restants} jours restants)"

    @property
    def jours_restants(self):
        """Retourne le nombre de jours restants avant expiration"""
        if self.est_stagiaire and self.date_expiration:
            delta = self.date_expiration - timezone.now()
            return max(delta.days, 0)
        return None
    
    @property
    def duree_service(self):
        """Retourne la durée de service depuis la mise en service"""
        if self.est_stagiaire and self.date_mise_service:
            delta = timezone.now() - self.date_mise_service
            return delta.days
        return None
    
    @property
    def periode_stage_ecoulee(self):
        """Pourcentage de la période de stage écoulée"""
        if (self.est_stagiaire and self.date_mise_service and self.date_expiration and
            self.date_expiration > self.date_mise_service):
            
            duree_totale = (self.date_expiration - self.date_mise_service).days
            duree_ecoulee = (timezone.now() - self.date_mise_service).days
            
            # Éviter les divisions par zéro et les pourcentages > 100%
            if duree_totale > 0:
                pourcentage = min(100, int((duree_ecoulee / duree_totale) * 100))
                return pourcentage
        return 0
    
    @property
    def statut_stagiaire(self):
        """Retourne le statut du stagiaire avec plus de détails"""
        if not self.est_stagiaire:
            return "Non applicable"
        
        if self.est_expire:
            return f"Expiré le {self.date_expiration.strftime('%d/%m/%Y')}"
        
        return (f"En cours ({self.jours_restants}j restants, "
                f"débuté le {self.date_mise_service.strftime('%d/%m/%Y')})")
    @property
    def full_name(self):
        """Retourne le nom complet de l'agent"""
        return self.user.get_full_name() or self.user.username

    @property
    def est_direction(self):
        """Vérifie si l'agent fait partie de la direction"""
        return self.type_agent == 'direction'

    @property
    def est_superviseur(self):
        """Vérifie si l'agent est un superviseur"""
        return self.type_agent == 'entrepot'

    @property
    def est_agent_terrain(self):
        """Vérifie si l'agent est un agent terrain"""
        return self.type_agent == 'terrain'

    @property
    def total_ventes(self):
        """Total de toutes les ventes de l'agent"""
        ventes = Vente.objects.filter(agent=self)
        return sum(vente.total_vente for vente in ventes)
    
    # Ventes réalisées par les stagiaires sous sa tutelle
    @property
    def total_ventes_stagiaires(self):
        """Total des ventes réalisées par les stagiaires sous sa tutelle"""
        if self.est_agent_terrain or self.est_superviseur:
            ventes_stagiaires = Vente.objects.filter(stagiaire__isnull=False, agent=self)
            return sum(vente.total_vente for vente in ventes_stagiaires)
        return 0
    
    #  Ventes personnelles (hors stagiaires)
    @property
    def total_ventes_personnelles(self):
        """Total des ventes réalisées personnellement (sans stagiaire)"""
        ventes_personnelles = Vente.objects.filter(agent=self, stagiaire__isnull=True)
        return sum(vente.total_vente for vente in ventes_personnelles)
    
    # Nombre de stagiaires supervisés
    @property
    def nombre_stagiaires_supervises(self):
        """Nombre de stagiaires distincts supervisés"""
        if self.est_agent_terrain or self.est_superviseur:
            return Vente.objects.filter(agent=self, stagiaire__isnull=False).values('stagiaire').distinct().count()
        return 0
    @property
    def total_recouvre(self):
        """Total déjà recouvré auprès de l'agent"""
        recouvrements = Recouvrement.objects.filter(agent=self)
        return sum(recouvrement.montant_recouvre for recouvrement in recouvrements)
    
    @property
    def argent_en_possession(self):
        """Argent que l'agent a encore en sa possession"""
        return self.total_ventes - self.total_recouvre
    
    @property
    def peut_etre_recouvre(self):
        """Vérifie s'il reste de l'argent à recouvrir"""
        return self.argent_en_possession > 0
    
    @property
    def peut_acceder_admin(self):
        """Vérifie si l'agent peut accéder à l'administration"""
        return self.est_direction or self.est_superviseur


    # PROPRIÉTÉS FINANCIÈRES POUR SUPERVISEUR - CORRIGÉES
    @property
    def total_argent_recouvre_et_ventes(self):
        """Total des entrées (recouvrements + ventes personnelles)"""
        if self.est_superviseur:
            recouvrements_agents = Recouvrement.objects.filter(superviseur=self)
            total_recouvrements = sum(r.montant_recouvre for r in recouvrements_agents)
            return total_recouvrements + self.total_ventes
        return 0

    @property
    def total_depenses_vente(self):
        """Total des dépenses impactant le solde vente"""
        if self.est_superviseur:
            # Toutes les dépenses impactent le solde vente
            return Depense.objects.filter(
                versement__superviseur=self
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
        return 0

    @property
    def total_versements_vente(self):
        """Total des versements impactant le solde vente"""
        if self.est_superviseur:
            return self.versements_bancaires.aggregate(
                total=Sum('montant_vente')
            )['total'] or Decimal('0.00')
        return 0

    @property
    def solde_vente_superviseur(self):
        """Solde actuel pour les ventes"""
        if not self.est_superviseur:
            return 0
        
        entrees = self.total_argent_recouvre_et_ventes
        versements = self.total_versements_vente
        depenses = self.total_depenses_vente
        
        return entrees - versements - depenses + self.ajustement_solde

    # PROPRIÉTÉS DE COMPATIBILITÉ (pour la vue existante)
    @property
    def total_depenses_superviseur(self):
        """Alias pour total_depenses_vente"""
        return self.total_depenses_vente

    @property
    def total_versements_bancaires(self):
        """Alias pour total_versements_vente"""
        return self.total_versements_vente

    @property
    def solde_superviseur(self):
        """Alias pour solde_vente_superviseur"""
        return self.solde_vente_superviseur

    # Autres propriétés existantes...
    @property
    def total_depenses_hors_vente(self):
        """Total des dépenses hors vente"""
        if self.est_superviseur:
            return Decimal('0.00')  # Simplifié pour l'instant
        return 0

    @property
    def total_versements_hors_vente(self):
        """Total des versements hors vente"""
        if self.est_superviseur:
            return self.versements_bancaires.aggregate(
                total=Sum('montant_hors_vente')
            )['total'] or Decimal('0.00')
        return 0

    @property
    def detail_solde_superviseur(self):
        """Détail complet du solde du superviseur"""
        if not self.est_superviseur:
            return {}
        
        return {
            'total_ventes_personnelles': self.total_ventes,
            'total_ventes_stagiaires': self.total_ventes_stagiaires,
            'total_recouvrements_agents': self.total_argent_recouvre_et_ventes - self.total_ventes,
            'total_entrees_vente': self.total_argent_recouvre_et_ventes,
            'total_depenses_vente': self.total_depenses_vente,
            'total_versements_vente': self.total_versements_vente,
            'solde_vente_actuel': self.solde_vente_superviseur,
            'total_depenses_hors_vente': self.total_depenses_hors_vente,
            'total_versements_hors_vente': self.total_versements_hors_vente,
        }
    
    @property
    def argent_disponible_pour_versement_vente(self):
        """Argent réellement disponible pour un nouveau versement lié aux ventes"""
        if not self.est_superviseur:
            return 0
        return max(self.solde_vente_superviseur, 0)
    
    @property
    def dernier_versement_superviseur(self):
        """Dernier versement effectué par le superviseur (compatibilité)"""
        if self.est_superviseur:
            dernier = VersementBancaire.objects.filter(superviseur=self).order_by('-date_versement_reelle').first()
            if dernier:
                return {
                    'versement': dernier,
                    'type': dernier.type_versement,  # ✅ Propriété calculée
                    'montant_verse': dernier.montant_total,  # ✅ Alias pour compatibilité
                    'depenses_associees': dernier.total_depenses_associees,
                    'date': dernier.date_versement_reelle
                }
        return None

    @property
    def versements_recents_superviseur(self):
        """Versements récents du superviseur (5 derniers)"""
        if self.est_superviseur:
            return VersementBancaire.objects.filter(superviseur=self).order_by('-date_versement_reelle')[:5]
        return VersementBancaire.objects.none()
    
    @property
    def bonus_total(self):
        """Retourne le bonus total de l'agent"""
        if hasattr(self, 'bonus'):
            return self.bonus.total_bonus
        return 0
    
    @property
    def nombre_ventes_avec_bonus(self):
        """Retourne le nombre de ventes éligibles au bonus"""
        if hasattr(self, 'bonus'):
            return self.bonus.get_ventes_avec_bonus().count()
        return 0
    


class DistributionAgent(models.Model):
    TYPE_DISTRIBUTION = (
        ('TERRAIN', 'Distribution à un agent '),
        ('AUTO', 'Auto-distribution '),
        ('STAGIAIRE', 'Distribution à un stagiaire'),
    )
    
    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="distributions_envoyees"
    )
    agent_terrain = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="distributions_recues",
        null=True,
        blank=True
    )
    type_distribution = models.CharField(
        max_length=50, 
        choices=TYPE_DISTRIBUTION,
        default='TERRAIN'
    )
    
    # Champs immuables pour l'historique
    quantite_totale = models.DecimalField(default=0, 
                                           max_digits=10, 
                                           decimal_places=2, 
                                           verbose_name="Quantité totale distribuée"
                                           )
    valeur_gros_totale = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Valeur totale (gros)"
    )
    valeur_detail_totale = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name="Valeur totale (détail)"
    )
    nombre_produits_differents = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de produits différents"
    )
    
    date_distribution = models.DateTimeField(default=timezone.now)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")
    est_retroactive = models.BooleanField(default=False)
    
    # Soft delete
    est_supprime = models.BooleanField(default=False, verbose_name="Supprimé")
    date_suppression = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")
    raison_suppression = models.TextField(blank=True, verbose_name="Raison de la suppression")
    
    # Audit des modifications
    nombre_modifications = models.PositiveIntegerField(default=0, verbose_name="Nombre de modifications")
    derniere_modification_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='distributions_modifiees',
        verbose_name="Dernière modification par"
    )

    def __str__(self):
        if self.est_supprime:
            return f"[SUPPRIMÉ] Distribution {self.id} de {self.superviseur}"
        elif self.type_distribution == 'AUTO':
            return f"Auto-distribution {self.id} de {self.superviseur}"
        else:
            return f"Distribution {self.id} de {self.superviseur} → {self.agent_terrain}"

    def save(self, *args, **kwargs):
        # ✅ Détermination automatique du type de distribution
        if self.agent_terrain:
            if self.agent_terrain.type_agent == 'stagiaire':
                self.type_distribution = 'STAGIAIRE'
            elif self.agent_terrain == self.superviseur:
                self.type_distribution = 'AUTO'
            else:
                self.type_distribution = 'TERRAIN'
        else:
            if self.type_distribution == 'AUTO':
                self.agent_terrain = self.superviseur

        # Compte les modifications
        if self.pk:
            self.nombre_modifications += 1

        super().save(*args, **kwargs)

    def soft_delete(self, user=None, raison=""):
        """Soft delete de la distribution"""
        self.est_supprime = True
        self.date_suppression = timezone.now()
        self.raison_suppression = raison
        if user:
            self.derniere_modification_par = user
        self.save()
        
        # Soft delete des détails associés
        self.detaildistribution_set.update(est_supprime=True)

    def restaurer(self, user=None):
        """Restaurer une distribution supprimée"""
        self.est_supprime = False
        self.date_suppression = None
        self.raison_suppression = ""
        if user:
            self.derniere_modification_par = user
        self.save()
        
        # Restaurer les détails associés
        self.detaildistribution_set.update(est_supprime=False)

    def _mettre_a_jour_totaux(self, user=None):
        """Met à jour les totaux immuables de la distribution"""
        from django.db import transaction
        
        with transaction.atomic():
            # Recharger l'objet pour éviter les problèmes de concurrence
            distribution = DistributionAgent.objects.select_for_update().get(pk=self.pk)
            details = distribution.detaildistribution_set.filter(est_supprime=False)
            
            # Calculer les nouveaux totaux
            quantite_totale = sum(detail.quantite for detail in details)
            valeur_gros_totale = sum((detail.prix_gros or 0) * detail.quantite for detail in details)
            valeur_detail_totale = sum((detail.prix_detail or 0) * detail.quantite for detail in details)
            nombre_produits_differents = details.values('lot__produit').distinct().count()
            
            # Mettre à jour les champs immuables
            DistributionAgent.objects.filter(pk=self.pk).update(
                quantite_totale=quantite_totale,
                valeur_gros_totale=valeur_gros_totale,
                valeur_detail_totale=valeur_detail_totale,
                nombre_produits_differents=nombre_produits_differents,
                date_modification=timezone.now(),
                derniere_modification_par=user
            )
            
            # Recharger l'instance
            self.refresh_from_db()

    @property
    def est_modifie(self):
        """Vérifie si la distribution a été modifiée"""
        return self.nombre_modifications > 0

    @property
    def statut(self):
        """Retourne le statut de la distribution"""
        if self.est_supprime:
            return "supprime"
        elif self.est_modifie:
            return "modifie"
        else:
            return "actif"

    class Meta:
        ordering = ['-date_distribution']
        verbose_name = "Distribution"
        verbose_name_plural = "Distributions"

class DetailDistribution(models.Model):
    distribution = models.ForeignKey(DistributionAgent, on_delete=models.CASCADE)
    lot = models.ForeignKey(LotEntrepot, on_delete=models.CASCADE)
    quantite = models.DecimalField(default=0, 
                                           max_digits=10, 
                                           decimal_places=2, 
                                           verbose_name="Quantité totale distribuée"
                                           )
    quantite_vendue = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0
    )

    # Prix fixés par le superviseur
    prix_gros = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prix_detail = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    specification = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Spécification (forme, présentation, etc.)"
    )
    # Soft delete
    est_supprime = models.BooleanField(default=False)
    date_suppression = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        spec_info = f" - {self.specification}" if self.specification else ""
        return f"{self.lot.produit.nom} : Qt - {self.quantite} {spec_info}"

    @property
    def quantite_restante_calculee(self):
        """
        Calcule la quantité restante en soustrayant les ventes déjà effectuées
        """
        from django.db.models import Sum
        
        # Quantité totale déjà vendue pour ce détail de distribution
        quantite_vendue = Vente.objects.filter(
            detail_distribution=self,
            est_supprime=False
        ).aggregate(total=Sum('quantite'))['total'] or 0
        
        return self.quantite - quantite_vendue
    class Meta:
        verbose_name = "Détail de distribution"
        verbose_name_plural = "Détails de distribution"


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
    detail_distribution = models.ForeignKey(
        'DetailDistribution', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Détail de distribution lié"
    )
    type_mouvement = models.CharField(max_length=50, choices=TYPE_MOUVEMENT)
    quantite =models.DecimalField(default=0, 
                                           max_digits=10, 
                                           decimal_places=2, 
                                           verbose_name="Quantité totale distribuée"
                                           )
    date_mouvement = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.type_mouvement} - {self.produit.nom} - {self.quantite}"

    class Meta:
        ordering = ['-date_mouvement']
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"

class JournalModificationDistribution(models.Model):
    TYPE_ACTION = (
        ('CREATION', 'Création'),
        ('MODIFICATION', 'Modification'),
        ('SUPPRESSION', 'Suppression'),
        ('RESTAURATION', 'Restauration'),
    )
    
    distribution = models.ForeignKey(DistributionAgent, on_delete=models.CASCADE)
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    type_action = models.CharField(max_length=50, choices=TYPE_ACTION)
    date_action = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True)
    anciennes_valeurs = models.JSONField(null=True, blank=True)
    nouvelles_valeurs = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.type_action} - Distribution #{self.distribution.id} par {self.utilisateur}"
    
    class Meta:
        ordering = ['-date_action']
        verbose_name = "Journal des modifications"
        verbose_name_plural = "Journal des modifications"

class Facture(models.Model):

    TYPE_FACTURE_CHOICES = [
        ('entree', 'Facture Entrée - Fournisseur'),
        ('depot', 'Dépôt Banque - Versement'),
    ]
    
    type_facture = models.CharField(max_length=50, choices=TYPE_FACTURE_CHOICES)
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
        limit_choices_to={'type_agent__in': ['terrain', 'entrepot']}
    )
    stagiaire = models.ForeignKey(
        Agent, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        limit_choices_to={'type_agent': 'stagiaire'},  # Uniquement les stagiaires
        related_name='ventes_realisees'
    )
    client = models.ForeignKey(Client,
                                on_delete=models.SET_NULL,
                                null=True,
                                blank=True)
    detail_distribution = models.ForeignKey(DetailDistribution, on_delete=models.CASCADE)
    specification = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Spécification du produit"
    )   
    quantite = models.DecimalField(
    max_digits=10,      
    decimal_places=2,   # Chiffres après la virgule
    default=Decimal('0.00')
)
    type_vente = models.CharField(max_length=50, choices=TYPE_VENTE_CHOICES, default='detail')
    prix_vente_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    mode_paiement = models.CharField(max_length=50, choices=MODE_PAIEMENT_CHOICES, default='comptant')
    
    # Date de la vente (peut être rétroactive)
    date_vente = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de la vente"
    )
    ancienne_vente = models.BooleanField(default=False)
    # Date d'enregistrement dans le système
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'enregistrement"
    )
    # Soft delete
    est_supprime = models.BooleanField(default=False, verbose_name="Supprimé")
    date_suppression = models.DateTimeField(null=True, blank=True, verbose_name="Date de suppression")

    def __str__(self):
        montant = int(self.total_vente)  # Supprime .0000
        date_str = self.date_vente.strftime("%Y-%m-%d %H:%M")
    
        base_str = f"vente {self.detail_distribution.lot} - {self.quantite} - {montant} FCFA - {date_str}"
    
        if self.stagiaire:
            return f"{base_str} [Stagiaire: {self.stagiaire.full_name}]"
    
        return base_str
    
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # 1️⃣ Déterminer automatiquement le prix
        if not self.prix_vente_unitaire:
            if self.type_vente == 'gros':
                self.prix_vente_unitaire = self.detail_distribution.prix_gros
            else:
                self.prix_vente_unitaire = self.detail_distribution.prix_detail

        # 2️⃣ Remplir automatiquement la spécification
        if self.detail_distribution and not self.specification:
            self.specification = self.detail_distribution.specification

        super().save(*args, **kwargs)

        # 3️⃣ Mise à jour du stock — seulement si nouvelle vente
        if is_new:
            dd = self.detail_distribution
            dd.quantite_vendue = dd.quantite_vendue + self.quantite
            dd.save(update_fields=['quantite_vendue'])

        # 4️⃣ Création automatique d’une dette
        if is_new and self.mode_paiement == 'credit' and not hasattr(self, 'dette'):
            Dette.objects.create(
                vente=self,
                montant_total=self.total_vente,
                montant_restant=self.total_vente,
                date_echeance=self.date_vente.date() + timedelta(days=30)
            )


    @property
    def total_vente(self):
        return (self.quantite or 0) * (self.prix_vente_unitaire or 0)

    class Meta:
        ordering = ['-date_vente']    
    @property
    def nom_client(self):
        """Retourne le nom du client ou 'Inconnu' si non spécifié"""
        if self.client and self.client.nom:
            return self.client.nom
        return "Inconnu"
    
    @property
    def produit_nom(self):
        return self.detail_distribution.lot.produit.nom
    
    @property
    def produit_complet(self):
        """Retourne le nom du produit avec sa spécification"""
        if self.specification:
            return f"{self.produit_nom} ({self.specification})"
        return self.produit_nom
    @property
    def total_vente(self):
        if self.quantite and self.prix_vente_unitaire:
            return self.quantite * self.prix_vente_unitaire
        return Decimal('0.00')
    
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
    
    @property
    def est_recouverte(self):
        """Vérifie si cette vente a été recouverte"""
        return self.agent.total_recouvre >= self.agent.total_ventes
      
    @property
    def est_retroactive(self):
        """Vérifie si c'est une vente rétroactive"""
        return self.date_vente.date() < self.date_creation.date()
    
    @property
    def vendeur_reel(self):
        """Retourne le vendeur réel (stagiaire ou agent)"""
        return self.stagiaire if self.stagiaire else self.agent
    
    @property
    def est_vente_stagiaire(self):
        """Vérifie si c'est une vente réalisée par un stagiaire"""
        return self.stagiaire is not None
    
    @property
    def nom_vendeur_complet(self):
        """Retourne le nom complet du vendeur avec indication stagiaire"""
        if self.stagiaire:
            return f"{self.stagiaire.full_name} (Stagiaire)"
        return self.agent.full_name

    @property
    def est_recouvrable_par_superviseur(self):
        """
        Vérifie si cette vente peut être recouvrée par un superviseur
        selon la règle métier : dette totalement recouvrée par l'agent
        """
        if self.mode_paiement != 'credit':
            return True  # Les ventes comptant sont toujours recouvrables
        
        if not hasattr(self, 'dette'):
            return True  # Pas de dette associée
            
        # La dette doit être totalement recouvrée (montant_restant = 0)
        return self.dette.montant_restant == 0
    
    @property
    def dette_recouvree_par_agent(self):
        """Montant que l'agent a déjà recouvré auprès du client"""
        if self.mode_paiement != 'credit' or not hasattr(self, 'dette'):
            return Decimal('0.00')
        return self.dette.montant_total - self.dette.montant_restant    
 
    
    class Meta:
        ordering = ['-date_vente']
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        

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
    statut = models.CharField(max_length=50, choices=STATUT_CHOICES, default='en_cours')
    
    # Informations de localisation détaillées
    nom_localite = models.CharField(max_length=100, blank=True)
    

    notes = models.TextField(blank=True)
    
    def __str__(self):
        client_nom = self.vente.client.nom if self.vente and self.vente.client else "Client inconnu"
        return f"Dette {self.montant_restant}€ - {client_nom} - {self.nom_localite}"

    def save(self, *args, **kwargs):
        # Mettre à jour automatiquement le statut
        if self.montant_restant <= 0:
            ancien_statut = self.statut
            self.statut = 'paye'
            self.date_reglement = timezone.now().date()

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
    mode_paiement = models.CharField(max_length=50, choices=MODE_PAIEMENT_CHOICES, default='espece')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    

    def __str__(self):
        client_nom = self.dette.vente.client.nom if self.dette and self.dette.vente and self.dette.vente.client else "Client inconnu"
        return f"Paiement {self.montant}€ - {client_nom}"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Mettre à jour le montant restant de la dette
        if is_new:
            ancien_montant_restant = self.dette.montant_restant
            self.dette.montant_restant -= self.montant
            
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
        return f"Bonus {self.nombre_produits_recouverts} produits - {self.agent.full_name}"

    def ajouter_bonus(self, montant, nb_produits):
        """Ajoute un bonus et le nombre de produits"""
        self.total_bonus += montant
        self.nombre_produits_recouverts += nb_produits
        self.save()

    # 👉 MÉTHODE MANQUANTE (nécessaire au dashboard)
    def get_produits_recouverts_par_mois(self, mois=None, annee=None):
        """Retourne le nombre de produits recouverts (bonus) pour un mois donné"""
        from datetime import datetime
        
        if mois is None:
            mois = timezone.now().month
        if annee is None:
            annee = timezone.now().year

        # Trouver les recouvrements éligibles dans ce mois
        recouvrements = Recouvrement.objects.filter(
            agent=self.agent,
            bonus_accorde=True,
            date_recouvrement__month=mois,
            date_recouvrement__year=annee
        )

        # Additionner les quantités des ventes liées
        total = sum(r.vente.quantite for r in recouvrements)

        return total

 
class Recouvrement(models.Model):
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'terrain'},
        related_name='recouvrements'
    )
    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='recouvrements_effectues',
        null=True,  # ⬅️ AJOUTER NULL=True
        blank=True  # ⬅️ AJOUTER blank=True
    
    )
    vente = models.ForeignKey(
    Vente,
    on_delete=models.CASCADE,
    blank=True,
    null=True
    )

    
    montant_recouvre = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Montant recouvré"
    )
    
    commentaire = models.TextField(blank=True)
    date_recouvrement = models.DateTimeField(default=timezone.now)
    date_creation = models.DateTimeField(auto_now_add=True)
    bonus_accorde = models.BooleanField(default=False)
    montant_bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def __str__(self):
        return f"Recouvrement {self.id} - {self.agent} - {self.montant_recouvre} FCFA"
    
    def calculer_bonus(self):
    
        # ⚠️ Empêche l’erreur : si pk n’existe pas, on sauvegarde d’abord
        if not self.pk:
            super().save()
    
        if self.vente.type_vente != "detail":
            self.bonus_accorde = False
            self.montant_bonus = Decimal("0.00")
            self.save(update_fields=["bonus_accorde", "montant_bonus"])
            return
    
        limite_bonus = self.vente.date_vente + timedelta(hours=48)
    
        if self.date_recouvrement <= limite_bonus:
            self.bonus_accorde = True
            self.montant_bonus = self.vente.quantite * Decimal("100")
            self.save(update_fields=["bonus_accorde", "montant_bonus"])
    
            bonus_agent, _ = BonusAgent.objects.get_or_create(agent=self.agent)
            bonus_agent.ajouter_bonus(
                montant=self.montant_bonus,
                nb_produits=self.vente.quantite
            )
    

    class Meta:
        ordering = ['-date_recouvrement']
        verbose_name = "Recouvrement"
        verbose_name_plural = "Recouvrements"
    

         

class VersementBancaire(models.Model):
    superviseur = models.ForeignKey(
        'Agent',
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='versements_bancaires'
    )

    montant_vente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Montant provenant de la vente"
    )

    montant_hors_vente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Montant hors vente"
    )

    description = HTMLField(
        blank=True,
        verbose_name="Description du versement"
    )

    date_versement_reelle = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date réelle du versement"
    )
    
    # PROPRIÉTÉS CALCULÉES - AJOUTEZ CES PROPRIÉTÉS
    @property
    def type_versement(self):
        """Détermine le type de versement basé sur les montants"""
        if self.montant_vente > 0 and self.montant_hors_vente > 0:
            return 'mixte'
        elif self.montant_vente > 0:
            return 'vente'
        elif self.montant_hors_vente > 0:
            return 'autre'
        else:
            return 'aucun'

    @property
    def montant_total(self):
        """Montant total du versement"""
        return self.montant_vente + self.montant_hors_vente

    @property
    def total_depenses_associees(self):
        """Total des dépenses associées"""
        return self.depenses.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    
    @property
    def recus_count(self):
        """Nombre de reçus associés"""
        return self.recus.count()
    
    def __str__(self):
        return f"Versement {self.id} - {self.superviseur} - {self.montant_total} FCFA"

    class Meta:
        ordering = ['-date_versement_reelle']


class RecuVersement(models.Model):
    versement = models.ForeignKey(
        VersementBancaire,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recus',
        verbose_name="Versement associé"
    )
    
    fichier = models.FileField(
        upload_to='recu_versement/%Y/%m/',
        verbose_name="Fichier reçu"
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Description du reçu"
    )
    
    date_upload = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'upload"
    )
    
    def __str__(self):
        return f"Reçu {self.id} - Versement {self.versement.id if self.versement else 'Aucun'}"
    
    
    class Meta:
        ordering = ['-date_upload']
        verbose_name = "Reçu de versement"
        verbose_name_plural = "Reçus de versement"


class Depense(models.Model):
    versement = models.ForeignKey(
        VersementBancaire,
        on_delete=models.CASCADE,
        related_name='depenses'
    )

    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant de la dépense",
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    description = HTMLField(
        verbose_name="Détails de la dépense"
    )

    date_depense = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de la dépense"
    )
    date_creation = models.DateTimeField(auto_now_add=True)



    def __str__(self):
        return f"Dépense {self.id} - {self.montant} FCFA "

    class Meta:
        ordering = ['-date_depense']
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"