from django.db import models
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from environs import ValidationError
from tinymce.models import HTMLField
from datetime import date, timedelta

from django.db.models import (
    Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
)
from django.db.models.functions import Coalesce
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_FLOOR

from dateutil.relativedelta import relativedelta
from django.utils import formats


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

    poids_unitaire_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Poids standard d’une unité (carton/sac). Laisser vide si produit non conditionné."
    )

    def __str__(self):
        return f"{self.nom}"

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
    
    @property
    def dette_totale(self):
        """Dette totale (ventes * prix achat)"""
        total = 0
        for lot in self.lots.all():
            for vente in lot.ventes.all():
                total += vente.quantite * lot.prix_achat_unitaire
        return Decimal(total)
    
    @property
    def total_paye(self):
        """Somme de tous les paiements"""
        total = self.paiements.aggregate(
            total=models.Sum('montant')
        )['total'] or 0
        return Decimal(total)
    
    @property
    def dette_restante(self):
        return max(
            self.dette_consomme - self.total_paye,
            Decimal('0.00')
        )

    @property
    def dette_contractuelle(self):
        return self.lots.aggregate(
            total=Sum(F('quantite_initiale') * F('prix_achat_unitaire'))
        )['total'] or Decimal('0.00')

    @property
    def dette_consomme(self):
        from core.models import Vente
        return Vente.objects.filter(
            detail_distribution__lot__fournisseur=self
        ).aggregate(
            total=Sum(
                F('quantite') *
                F('detail_distribution__lot__prix_achat_unitaire')
            )
        )['total'] or Decimal('0.00')


class Agent(models.Model):
    """
    RÈGLES FINANCIÈRES (POST-TRANSITION)

    - Le solde OPÉRATIONNEL est calculé uniquement via :
      - recouvrements agents
      - ventes personnelles autorisées
      - versements_vente

    - Les champs suivants sont ANALYTIQUES :
      - montant_hors_vente
      - dépenses
      - total_versements_superviseur

    Toute modification doit respecter cette séparation.
    """

    TYPE_AGENT_CHOICES = (
        ('direction', 'Direction'),
        ('rot', 'Responsable Opérations'),
        ('entrepot', 'Superviseur'),
        ('terrain', 'Mamy'),
        ('agent_gros', 'Agent (Vente en Gros)'), 
        ('stagiaire', 'Stagiaire'), 
    )
    TYPE_CONTRAT_CHOICES = (
    ('prestation', 'Contrat de prestation'),
    ('stage', 'Stage'),
    ('cdd', 'CDD'), 
    ('cdi', 'CDI'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    type_agent = models.CharField(max_length=50, choices=TYPE_AGENT_CHOICES)
    superviseur = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='agents_geres'
    )
    date_debut_fonction = models.DateField(
        null=True,
        blank=True,
        help_text="Date de prise de fonction (superviseur / agent)"
    )
    # Agent
    salaire_base_personnel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override du salaire de base (si vide → règle générale)"
    )


    quartier = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Quartier d'affectation"
    )

    marche_affectation = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Marché d'affectation"
    )

    # 📄 Contrat
    type_contrat = models.CharField(
        max_length=20,
        choices=TYPE_CONTRAT_CHOICES,
        default='prestation',
        verbose_name="Type de contrat"
    )

    date_fin_contrat = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de fin de contrat"
    )
    telephone = models.CharField(max_length=50, blank=True, null=True)
    ajustement_solde = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Ajustement manuel du solde (+/- FCFA)"
    )
    est_actif = models.BooleanField(
        default=True,
        help_text="Agent actif sur la plateforme"
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

        # =========================
        # LOGIQUE STAGIAIRE (existant)
        # =========================
        if self.type_agent == 'stagiaire':
            if not self.date_mise_service:
                self.date_mise_service = timezone.now()
            if not self.date_expiration:
                self.date_expiration = self.date_mise_service + timedelta(days=14)

        elif self.type_agent != 'stagiaire':
            if not self.user.is_active:
                self.user.is_active = True
                self.user.save(update_fields=['is_active'])
            self.date_expiration = None
            self.date_mise_service = None

        # =========================
        # LOGIQUE CONTRAT (NOUVEAU)
        # =========================

        # 🔹 Prestation : 1 mois par défaut
        if self.type_contrat == 'prestation':
            if not self.date_fin_contrat:
                self.date_fin_contrat = (
                    self.date_creation.date()
                    if self.pk else timezone.now().date()
                ) + relativedelta(months=1)

        # 🔹 CDI : jamais de date de fin
        if self.type_contrat == 'cdi':
            self.date_fin_contrat = None

        super().save(*args, **kwargs)


    def clean(self):
        if self.type_contrat == 'cdd' and not self.date_fin_contrat:
            raise ValidationError("Un CDD doit avoir une date de fin.")

        if self.type_contrat == 'cdi' and self.date_fin_contrat:
            raise ValidationError("Un CDI ne doit pas avoir de date de fin.")


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

    def desactiver(self):
        self.est_actif = False
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.save(update_fields=['est_actif'])

    def activer(self):
        self.est_actif = True
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        self.save(update_fields=['est_actif'])
    
    def remettre_solde_operationnel_a_zero(self, cloture=None, par=None):
        """
        Remet à zéro le solde OPÉRATIONNEL du superviseur
        après une clôture mensuelle ou de transition.
        """
    
        if not self.est_superviseur:
            return
    
        solde_actuel = self.solde_reel_superviseur  # ✅ BON SOLDE
    
        if solde_actuel == 0:
            return
    
        # Neutralisation comptable via ajustement
        self.ajustement_solde -= solde_actuel
        self.save(update_fields=['ajustement_solde'])
    
        # Traçabilité
        if cloture:
            AjustementSolde.objects.create(
                agent=self,
                montant=-solde_actuel,
                motif="Remise à zéro du solde opérationnel après clôture",
                cloture=cloture
            )
    

    def __str__(self):
        return f"{self.full_name} - {self.get_type_agent_display()}"
    

    @property
    def contrat_expire(self):
        if self.date_fin_contrat:
            return timezone.now().date() > self.date_fin_contrat
        return False

    @property
    def est_expire(self):
        """Vérifie si le stagiaire a dépassé sa date d’expiration"""
        if self.type_agent == 'stagiaire' and self.date_expiration:
            return timezone.now() > self.date_expiration
        return False

    @property
    def a_acces_plateforme(self):
        if not self.est_actif:
            return False
    
        if self.type_agent == 'stagiaire':
            return not self.est_expire
    
        return True
    
    
    @property
    def statut_stagiaire(self):
        """Retourne le statut du stagiaire"""
        if not self.est_stagiaire:
            return "Non applicable"
        if self.est_expire:
            return "Expiré"
        return f"Valide ({self.jours_restants} jours restants)"
    
    @property
    def est_stagiaire(self):
        """Vérifie si l'agent est un stagiaire"""
        return self.type_agent == 'stagiaire'

    @property
    def nombre_stagiaires_supervises(self):
        """Nombre de stagiaires distincts supervisés"""
        if self.est_agent_terrain or self.est_superviseur:
            return Vente.objects.filter(agent=self, stagiaire__isnull=False).values('stagiaire').distinct().count()
        return 0

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
    def peut_acceder_admin(self):
        """Vérifie si l'agent peut accéder à l'administration"""
        return self.est_direction or self.est_superviseur

    @property
    def full_name(self):
        """Retourne le nom complet de l'agent"""
        return self.user.get_full_name() or self.user.username

    @property
    def est_direction(self):
        """Vérifie si l'agent fait partie de la direction"""
        return self.type_agent == 'direction'
    
    @property
    def est_rot(self):
        """Vérifie si l'agent est un rot"""
        return self.type_agent == 'rot'
    
    @property
    def est_superviseur(self):
        """Vérifie si l'agent est un superviseur"""
        return self.type_agent == 'entrepot'

    @property
    def est_agent_terrain(self):
        """Vérifie si l'agent est un agent terrain"""
        return self.type_agent == 'terrain'

    @property
    def est_superviseur_ou_rot(self):
        return self.type_agent in ['entrepot', 'rot']
    
  
    @property
    def est_agent_gros(self):
        return self.type_agent == 'agent_gros'

    @property
    def est_agent_vente(self):
        return self.type_agent in ['terrain', 'agent_gros']

   
    @property
    def total_ventes(self):
        """
        Total des ventes réalisées par l’agent terrain
        """
        if not self.est_agent_vente:
            return Decimal("0.00")

        return (
            Vente.objects
            .filter(agent=self)
            .aggregate(
                total=Coalesce(
                    Sum(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal("0.00")
                )
            )["total"]
        )


    @property
    def total_recouvre(self):
        """
        Total déjà remis par l’agent terrain à son superviseur
        """
        if not self.est_agent_terrain:
            return Decimal("0.00")

        return (
            Recouvrement.objects
            .filter(agent=self)
            .aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
            )["total"]
        )


    @property
    def argent_en_possession(self):
        """
        Argent physiquement détenu par l’agent terrain
        """
        if not self.est_agent_vente:
            return Decimal("0.00")

        return self.total_ventes - self.total_recouvre


    @property
    def peut_etre_recouvre(self):
        """
        Indique si l’agent terrain a encore de l’argent à remettre
        """
        return self.est_agent_vente and self.argent_en_possession > 0

    #superviseur
    @property
    def total_recouvre_agents(self):
        """
        Argent récupéré par le superviseur auprès de ses agents terrain
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        return (
            Recouvrement.objects
            .filter(superviseur=self)
            .aggregate(
                total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
            )["total"]
        )

    @property
    def total_depenses_superviseur(self):
        """
        Dépenses engagées par le superviseur (transport, logistique, terrain…)
        """
        """
        ⚠️ OBSOLÈTE – dépenses interdites après transition
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        return (
            Depense.objects
            .filter(versement__superviseur=self)
            .aggregate(
                total=Coalesce(Sum("montant"), Decimal("0.00"))
            )["total"]
        )

    @property
    def total_versements_superviseur(self):
        """
        Argent déjà versé par le superviseur (banque ou ROT)
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        versements = VersementBancaire.objects.filter(superviseur=self).aggregate(
            vente=Coalesce(Sum("montant_vente"), Decimal("0.00")),
            hors_vente=Coalesce(Sum("montant_hors_vente"), Decimal("0.00")),
        )

        return versements["vente"] + versements["hors_vente"]

    @property
    def anciennes_ventes_personnelles(self):
        """
        ⚠️ TRANSITOIRE
        Ventes réalisées AVANT le changement de rôle
        À supprimer après clôture définitive
        """
        if not self.est_superviseur:
            return Decimal("0.00")
        if self.date_derniere_cloture:
            return Decimal("0.00")  # 🔒 bloqué après transition
        return (
            Vente.objects
            .filter(agent=self)
            .aggregate(
                total=Coalesce(
                    Sum(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField(max_digits=15, decimal_places=2)
                    ),
                    Decimal("0.00")
                )
            )["total"]
        )

    @property
    def solde_reel_superviseur(self):
        """
        SOLDE RÉEL DU SUPERVISEUR (FORMULE OFFICIELLE)

        argent agents
        + anciennes ventes personnelles
        - dépenses
        - versements
        ± ajustement manuel
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        if self.date_derniere_cloture:
            return Decimal("0.00")  # 🔒 ancien monde fermé

        return (
            self.total_recouvre_agents
            + self.anciennes_ventes_personnelles
            - self.total_depenses_superviseur
            - self.total_versements_superviseur
            + (self.ajustement_solde or Decimal("0.00"))
        )

    @property
    def total_versements_vente(self): 
        """Total des versements impactant le solde vente""" 
        if self.est_superviseur: 
            return self.versements_bancaires.aggregate(
                 total=Sum('montant_vente') 
                 )['total'] or Decimal('0.00')
            return 0

    @property
    def date_derniere_cloture(self):
        derniere = (
            ClotureMensuelle.objects
            .filter(superviseur=self, est_cloture=True)
            .order_by('-date_fin_periode')
            .first()
        )
        return (
            derniere.date_fin_periode
            if derniere
            else date.min
        )
    
    
    @property
    def total_ventes_autorisees_superviseur(self):
        if not self.est_superviseur:
            return Decimal("0.00")

        return Vente.objects.filter(
            agent=self,
            date_vente__gte=self.date_derniere_cloture
        ).aggregate(
            total=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            )
        )["total"]

    @property
    def solde_transitoire_superviseur(self):
        """
        Solde de transit (cash temporairement détenu)
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        return (
            self.total_recouvre_agents
            + self.total_ventes_autorisees_superviseur
            - self.total_versements_vente
        )

    @property
    def solde_operationnel_superviseur(self):
        """
        SOLDE OPÉRATIONNEL ACTUEL DU SUPERVISEUR (POST-CLÔTURE)
    
        = cash réellement détenu aujourd’hui
        """
    
        if not self.est_superviseur:
            return Decimal("0.00")
    
        date_ref = self.date_derniere_cloture
    
        # 💰 Argent recouvré auprès des agents
        recouvre_agents = Recouvrement.objects.filter(
            superviseur=self,
            date_recouvrement__gt=date_ref
        ).aggregate(
            total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
        )["total"]
    
        # 🧾 Ventes personnelles AUTORISÉES (exception terrain)
        ventes_perso = Vente.objects.filter(
            agent=self,
            date_vente__gt=date_ref
        ).aggregate(
            total=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            )
        )["total"]
    
        # 🏦 Argent déjà remis au ROT (VENTE SEULEMENT)
        versements_vente = VersementBancaire.objects.filter(
            superviseur=self,
            date_versement_reelle__gt=date_ref
        ).aggregate(
            total=Coalesce(Sum("montant_vente"), Decimal("0.00"))
        )["total"]
    
        return recouvre_agents + ventes_perso - versements_vente
    
    @property
    def cash_disponible_superviseur(self):
        """
        Cash réel disponible AVANT remise au ROT
        """
        if not self.est_superviseur:
            return Decimal("0.00")

        date_ref = self.date_derniere_cloture

        # Argent récupéré des agents
        cash_agents = Recouvrement.objects.filter(
            superviseur=self,
            date_recouvrement__gt=date_ref
        ).aggregate(
            total=Coalesce(Sum("montant_recouvre"), Decimal("0.00"))
        )["total"]

        # Ventes personnelles autorisées
        ventes_perso = Vente.objects.filter(
            agent=self,
            date_vente__gt=date_ref
        ).aggregate(
            total=Coalesce(
                Sum(F("quantite") * F("prix_vente_unitaire")),
                Decimal("0.00")
            )
        )["total"]

        # ❌ ON NE SOUSTRAIT PAS LES REMISES AU ROT ICI
        return cash_agents + ventes_perso

    
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
        related_name="lots",
        verbose_name="Fournisseur (optionnel)"
    )
    quantite_initiale = models.DecimalField(max_digits=10, decimal_places=2)
    quantite_restante = models.DecimalField(max_digits=10, decimal_places=2)
    prix_achat_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix par unité fournisseur (carton / sac OU kg si non conditionné)"
    )

    valeur_stock_initiale = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    receptionne_par = models.ForeignKey(
        Agent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lots_receptionnes"
    )

    date_reception = models.DateTimeField(default=timezone.now)
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    reference_lot = models.CharField(max_length=100, unique=True, blank=True, null=True) 



    def __str__(self):
        produit = self.produit.nom if self.produit else "Produit inconnu"
        fournisseur = self.fournisseur.nom if self.fournisseur else "—"
       
        return (
            f"{produit} | {fournisseur} | "
            f"reste {self.quantite_restante:.2f} "
            f"(init. {self.quantite_initiale:.2f})"
        )


    from decimal import Decimal
    from django.core.exceptions import ValidationError

    def save(self, *args, **kwargs):

        # --- Calcul valeur initiale UNE SEULE FOIS ---
        if self.valeur_stock_initiale is None:

            if self.est_conditionne:
                # prix par unité × nombre d’unités
                nb_unites = self.quantite_initiale / self.produit.poids_unitaire_kg
                self.valeur_stock_initiale = nb_unites * self.prix_achat_unitaire
            else:
                # produit vrac → prix au kg
                self.valeur_stock_initiale = self.quantite_initiale * self.prix_achat_unitaire

        # --- Garde-fous ---
        if self.quantite_restante > self.quantite_initiale:
            raise ValidationError("Quantité restante > quantité initiale")

        if self.quantite_restante < 0:
            raise ValidationError("Quantité restante négative")

        super().save(*args, **kwargs)

    @property
    def montant_total(self):
        if self.est_conditionne:
            nb_unites = self.quantite_initiale / self.produit.poids_unitaire_kg
            return nb_unites * self.prix_achat_unitaire
        return self.quantite_initiale * self.prix_achat_unitaire

    @property
    def valeur_actuelle_stock(self):
        if self.est_conditionne:
            nb_unites = self.quantite_restante / self.produit.poids_unitaire_kg
            return nb_unites * self.prix_achat_unitaire
        return self.quantite_restante * self.prix_achat_unitaire

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
   
    
    @property
    def total_paye_lot(self):
        """Somme des paiements pour ce lot"""
        total = self.paiements.aggregate(
            total=models.Sum('montant')
        )['total'] or 0
        return Decimal(total)
    
    @property
    def reste_a_payer_lot(self):
        """Ce qu'il reste à payer pour ce lot"""
        return max(self.dette_lot - self.total_paye_lot, Decimal(0))

    @property
    def chiffre_affaires_theorique_lot(self):
        """
        ca du lot basée sur les ventes réalisées
        """
        from django.db.models import Sum, F
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        from core.models import Vente

        total = Vente.objects.filter(
            detail_distribution__lot=self
        ).aggregate(
            total=Coalesce(
                Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')),
                Decimal('0.00')
            )
        )['total']

        return total or Decimal('0.00')
    
    @property
    def montant_total(self):
        return self.quantite_initiale * self.prix_achat_unitaire

    @property
    def total_facture_lot(self):
        return self.factures.aggregate(
            total=models.Sum('montant')
        )['total'] or Decimal('0')

    @property
    def est_solde(self):
        return self.total_facture_lot >= self.montant_total

    @property
    def est_conditionne(self):
        """
        Un lot est conditionné si le produit a un poids unitaire défini
        """
        return bool(self.produit and self.produit.poids_unitaire_kg)

    @property
    def quantite_restante_unites(self):
        """
        Nombre d’unités restantes (cartons / sacs)
        """
        if not self.est_conditionne:
            return None

        return (self.quantite_restante / self.produit.poids_unitaire_kg).quantize(
            Decimal("1"), rounding=ROUND_FLOOR
        )

    @property
    def quantite_initiale_unites(self):
        """
        Nombre d’unités initiales
        """
        if not self.est_conditionne:
            return None

        return (self.quantite_initiale / self.produit.poids_unitaire_kg).quantize(
            Decimal("1"), rounding=ROUND_FLOOR
        )


class FactureLotEntrepot(models.Model):
    lot = models.ForeignKey(
        LotEntrepot,
        on_delete=models.CASCADE,
        related_name='factures'
    )

    fichier = models.FileField(upload_to='factures_entrepot/%Y/%m/')
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    description = models.CharField(max_length=255, blank=True)
    date_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Facture {self.id} – Lot {self.lot.reference_lot}"


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


class AffectationLotSuperviseur(models.Model):
    lot = models.ForeignKey(LotEntrepot, on_delete=models.CASCADE)

    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='lots_affectes'
    )

    # 🔒 IMMUTABLE : quantité affectée au départ
    quantite_initiale = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # 🔁 MUTABLE : quantité restante chez le superviseur
    quantite_restante = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    prix_gros = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    prix_detail = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    attribue_par = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'type_agent': 'rot'},
        related_name='affectations_realisees'
    )

    date_affectation = models.DateTimeField(
        verbose_name="Date de distribution"
    )

    # 🔒 DATE TECHNIQUE (audit)
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    def date_affectation_humaine(self):
        """
        Date lisible pour affichage (sans heure)
        """
        return formats.date_format(
            self.date_affectation,
            "DATE_FORMAT"
        )
    def __str__(self):
        return (
            f"{self.lot.produit.nom} — "
            f"reste {self.quantite_restante:.2f} "
            f"(init. {self.quantite_initiale:.2f})"
            f"- {self.date_affectation_humaine()})"

        )



    def quantite_resume(self):
        """
        Résumé simple et uniforme de la quantité
        """
        return f"{self.quantite_restante:.2f} / {self.quantite_initiale:.2f}"



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
    
    
    def __str__(self):
       
        if self.type_distribution == 'AUTO':
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

        super().save(*args, **kwargs)


    class Meta:
        ordering = ['-date_distribution']
        indexes = [
            models.Index(fields=['date_distribution']),
            models.Index(fields=['superviseur']),
        ]
    


class DetailDistribution(models.Model):
    distribution = models.ForeignKey(
        DistributionAgent, 
        on_delete=models.CASCADE
        )
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

    # Prix hérités de l'affectation ROT (snapshot historique)
    prix_gros = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prix_detail = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    specification = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Spécification (forme, présentation, etc.)"
    )
    
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
        return f"Vente #{self.id} ({self.date_vente:%d/%m})"

    
    
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
 

    @property
    def quantite_en_kg(self):
        produit = self.detail_distribution.lot.produit

        if produit.poids_unitaire_kg:
            # produit conditionné
            return self.quantite * produit.poids_unitaire_kg

        # produit vrac
        return self.quantite

    
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
        limit_choices_to={'type_agent__in': ['terrain','agent_gros']},
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
    
    
    class Meta:
        ordering = ['-date_recouvrement']
        verbose_name = "Recouvrement"
        verbose_name_plural = "Recouvrements"
          

class RecouvrementSuperviseur(models.Model):
    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='recouvrements_rot'
    )

    rot = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'rot'},
        related_name='recouvrements_superviseurs'
    )

    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant remis au ROT"
    )

  

    commentaire = models.TextField(blank=True)

    date_recouvrement = models.DateTimeField(default=timezone.now)
    date_creation = models.DateTimeField(auto_now_add=True)


    def clean(self):
        if self.montant is None or self.superviseur is None:
            return
    
        if self.montant <= 0:
            raise ValidationError({'montant': "Le montant doit être positif."})
    
        cash_disponible = self.superviseur.cash_disponible_superviseur
    
        # ⚠️ IMPORTANT : exclure l’instance si modification
        if self.pk:
            deja_remis = RecouvrementSuperviseur.objects.filter(
                superviseur=self.superviseur
            ).exclude(pk=self.pk).aggregate(
                total=Coalesce(Sum("montant"), Decimal("0.00"))
            )["total"]
        else:
            deja_remis = Decimal("0.00")
    
        cash_restant = cash_disponible - deja_remis
    
        if self.montant > cash_restant:
            raise ValidationError({
                'montant': (
                    f"Montant supérieur au cash disponible "
                    f"({cash_restant:,.0f} FCFA)."
                )
            })
    

    def __str__(self):
        return (
            f"Recouvrement {self.montant} FCFA | "
            f"{self.superviseur.full_name} → {self.rot.full_name}"
        )

    class Meta:
        ordering = ['-date_recouvrement']
        verbose_name = "Recouvrement superviseur"
        verbose_name_plural = "Recouvrements superviseurs"


class VersementBancaire(models.Model):
    # ⛔ À déprécier
    superviseur = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='versements_bancaires',
        help_text="(OBSOLÈTE) Superviseur source du cash"
    )
    # ✅ NOUVELLE SOURCE DE VÉRITÉ
    effectue_par = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versements_effectues",
        limit_choices_to={'type_agent': 'rot'},
        help_text="ROT ayant réellement effectué le versement"
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
    def cash_depense_reel(self):
        """
        Cash réel consommé lors de ce versement
        = vente versée + dépenses payées
        """
        return (
            (self.montant_vente or Decimal("0.00"))
            + (self.total_depenses_associees or Decimal("0.00"))
        )

    @property
    def est_equilibre(self):
        """
        Vérifie si les dépenses sont couvertes par le hors vente
        (logique comptable)
        """
        return self.total_depenses_associees <= self.montant_hors_vente

    
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
    # Qui a effectué la dépense (ROT)
    effectue_par = models.ForeignKey(
        Agent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="depenses_effectuees",
        help_text="Agent ayant réellement effectué la dépense"
    )

    # Lien optionnel avec un versement (NE PAS CASSER L’EXISTANT)
    versement = models.ForeignKey(
        VersementBancaire,
        on_delete=models.SET_NULL,   
        null=True,
        blank=True,
        related_name='depenses',
        help_text="Versement éventuellement lié"
    )

    # Montant (inchangé)
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant de la dépense",
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    # 🟢 NOUVEAU : catégorie normalisée (MVP)
    categorie = models.CharField(
        max_length=40,
        choices=[
            ('ACHAT_MARCHANDISE', 'Achat marchandise'),
            ('TRANSPORT_MARCHANDISE', 'Transport marchandise'),
            ('CARBURANT', 'Carburant'),
            ('MAINTENANCE_VEHICULE', 'Maintenance véhicule'),
            ('FRAIS_OPERATIONNELS', 'Frais opérationnels'),
            ('TRANSFERT', 'Transfert'),
            ('DIVERS', 'Divers'),
        ],
        default='DIVERS',
        verbose_name="Catégorie"
    )

    # 🟢 NOUVEAU : note simple (terrain-friendly)
    note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Note (optionnelle)",
        help_text="Détail libre saisi par l’agent"
    )

    # 🔵 ANCIEN : description HTML (HISTORIQUE)
    description = HTMLField(
        blank=True,
        verbose_name="Description historique"
    )

    date_depense = models.DateTimeField(
        default=timezone.now,
        verbose_name="Date de la dépense"
    )

    date_creation = models.DateTimeField(
        auto_now_add=True
    )

    # 🟡 Technique : origine de la donnée
    source = models.CharField(
        max_length=20,
        default='ROT',
        choices=[
            ('ROT', 'Saisie terrain'),
            ('MIGRATION', 'Migration historique'),
            ('ADMIN', 'Correction admin'),
        ]
    )

    def __str__(self):
        return f"Dépense #{self.id} - {self.montant} FCFA"

    class Meta:
        ordering = ['-date_depense']
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"


class PaiementFournisseur(models.Model):
    """
    Paiement simple au fournisseur
    Objectif : traçabilité claire, pas de sur-modélisation
    """

    fournisseur = models.ForeignKey(
        'Fournisseur',
        on_delete=models.CASCADE,
        related_name='paiements'
    )

    lot = models.ForeignKey(
        'LotEntrepot',
        on_delete=models.CASCADE,
        related_name='paiements',
        null=True,
        blank=True,
        help_text="Optionnel : paiement rattaché à un lot précis"
    )

    superviseur = models.ForeignKey(
        'Agent',
        on_delete=models.SET_NULL,
        null=True,
        related_name='paiements_fournisseurs',
        limit_choices_to={'type_agent': 'entrepot'},
        verbose_name="Superviseur responsable"
    )

    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant payé"
    )

    # Date réelle du paiement (peut être rétroactive)
    date_paiement = models.DateField(
        verbose_name="Date du paiement"
    )

    # Métadonnées système
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='paiements_fournisseurs_crees'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Soft delete
    est_supprime = models.BooleanField(default=False)
    supprime_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements_fournisseurs_supprimes'
    )
    date_suppression = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date_paiement', '-created_at']
        verbose_name = "Paiement fournisseur"
        verbose_name_plural = "Paiements fournisseurs"

    def __str__(self):
        return f"{self.montant} FCFA – {self.fournisseur.nom} ({self.date_paiement})"

    def clean(self):
        if self.montant <= 0:
            raise ValidationError("Le montant doit être strictement positif.")

    def soft_delete(self, user=None, raison=""):
        """Soft delete du paiement"""
        self.est_supprime = True
        self.date_suppression = timezone.now()
        self.raison_suppression = raison
        if user:
            self.supprime_par = user
        self.save()
    
    def restaurer(self, user=None):
        """Restaurer un paiement supprimé"""
        self.est_supprime = False
        self.date_suppression = None
        self.raison_suppression = ""
        if user:
            self.supprime_par = None
        self.save()
    
    @property
    def statut(self):
        """Retourne le statut du paiement"""
        if self.est_supprime:
            return "supprime"
        return "actif"
    

class ClotureMensuelle(models.Model):
    """
    Clôture financière d'un superviseur sur une période donnée.
    La période n'est PAS forcément calendaire.
    """

    superviseur = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        limit_choices_to={'type_agent': 'entrepot'},
        related_name='clotures_mensuelles'
    )

    # Référence logique (pour classement / affichage)
    annee = models.IntegerField(verbose_name="Année de référence")
    mois = models.IntegerField(verbose_name="Mois de référence")

    # 🔑 PÉRIODE RÉELLE COUVERTE (FLEXIBLE)
    date_debut_periode = models.DateField(
        verbose_name="Début réel de la période"
    )
    date_fin_periode = models.DateField(
        verbose_name="Fin réelle de la période"
    )

    # 💰 SOLDES (CALCULÉS AUTOMATIQUEMENT)
    solde_ouverture = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Solde d'ouverture"
    )
    solde_cloture = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Solde de clôture"
    )

    # 🔒 VALIDATION HUMAINE
    est_cloture = models.BooleanField(
        default=False,
        verbose_name="Clôture validée"
    )
    date_cloture = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation de la clôture"
    )
    cloture_par = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='clotures_validees',
        verbose_name="Clôturée par"
    )
    ecart_post_cloture = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    default=0,
    verbose_name="Écart après clôture"
    )


    # 🧾 MÉTADONNÉES
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )

    class Meta:
        unique_together = ('superviseur', 'annee', 'mois')
        ordering = ['-annee', '-mois']
        verbose_name = "Clôture mensuelle"
        verbose_name_plural = "Clôtures mensuelles"

    def __str__(self):
        return (
            f"{self.superviseur.full_name} | "
            f"{self.mois:02d}/{self.annee} | "
            f"{self.date_debut_periode} → {self.date_fin_periode}"
        )

    @property
    def est_ouverte(self):
        return not self.est_cloture

    @property
    def duree_periode(self):
        """Nombre de jours couverts par la clôture"""
        return (self.date_fin_periode - self.date_debut_periode).days + 1

class AjustementSolde(models.Model):
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="ajustements_solde"
    )
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    motif = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    cloture = models.ForeignKey(
        ClotureMensuelle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ajustements"
    )

    def __str__(self):
        return f"{self.agent} | {self.montant} | {self.date:%d/%m/%Y}"



class RegleSalaire(models.Model):
    TYPE_AGENT_CHOICES = [
        ("terrain", "Agent terrain (mamy)"),
        ("agent_gros", "Agent gros"),
        ("superviseur", "Superviseur"),
    ]

    type_agent = models.CharField(max_length=20, choices=TYPE_AGENT_CHOICES, unique=True)

    dotation_fonction = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )

    incentive_par_kg = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    incentive_par_carton = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"Règle salaire — {self.get_type_agent_display()}"



class Salaire(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="salaires")

    date_debut = models.DateField()
    date_fin = models.DateField()

    salaire_base = models.DecimalField(max_digits=10, decimal_places=2)
    incentive = models.DecimalField(max_digits=10, decimal_places=2)
    salaire_total = models.DecimalField(max_digits=10, decimal_places=2)

    genere_le = models.DateTimeField(auto_now_add=True)
    valide = models.BooleanField(default=False)

    class Meta:
        unique_together = ("agent", "date_debut", "date_fin")
        ordering = ["-date_debut"]

    def __str__(self):
        return f"Salaire {self.agent.full_name} ({self.date_debut} → {self.date_fin})"
