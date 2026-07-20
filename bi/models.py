from django.conf import settings
from django.db import models

from core.models import Fournisseur, Produit


class AjustementPrixAchat(models.Model):
    """Calibration du prix d'achat fournisseur (dbt-2). Saisie admin Direction uniquement.

    Append-only : pas de suppression ni de modification une fois enregistré (voir
    BiAjustementPrixAchatAdmin) — un ajustement erroné s'annule par un contre-ajustement
    (nouvelle ligne, quantite_concernee négative ou prix corrigé mis à jour).

    fournisseur/annee/mois sont requis (pas de simple "fallback") : dbt_bi.fct_ventes
    n'expose pas lot_id (dérivation vente -> lot -> fournisseur uniquement, cf.
    dbt_bi/models/marts/fct_ventes.sql), donc la clé de jointure effective côté
    vw_marge_fournisseur est fournisseur x mois, pas le lot précis. reference_lot et
    produit ne servent qu'à la traçabilité de la saisie, pas à la vue dbt.
    """

    reference_lot = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Traçabilité optionnelle vers core_lotentrepot.reference_lot (texte libre, "
        "pas de FK — le lot peut être introuvable ou mal identifié au moment de la saisie).",
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ajustements_prix_achat",
        help_text="Traçabilité optionnelle, non utilisé par vw_marge_fournisseur (grain fournisseur x mois).",
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name="ajustements_prix_achat",
    )
    annee = models.PositiveSmallIntegerField()
    mois = models.PositiveSmallIntegerField()
    quantite_concernee = models.DecimalField(max_digits=10, decimal_places=2)
    prix_achat_corrige = models.DecimalField(max_digits=10, decimal_places=2)
    justification = models.TextField()
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ajustements_prix_achat_saisis",
    )
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ajustement prix d'achat"
        verbose_name_plural = "Ajustements prix d'achat"
        ordering = ["-date_saisie"]

    def __str__(self):
        return f"{self.fournisseur} — {self.mois:02d}/{self.annee} — {self.prix_achat_corrige} FCFA"


# --- Modèles managed=False : lecture des vues bi_ générées par dbt (dbt_bi/models/marts/aggregates).
# db_table utilise le style `'schema\".\"table'` : Django entoure la chaîne db_table d'une seule
# paire de guillemets (`quote_name`), donc injecter `".` dedans produit `"bi_"."vw_..."`, un
# identifiant schema-qualifié valide en PostgreSQL — pas besoin de search_path ni de router pour
# lire ces tables (voir docs/docs_bi/architecte/setup.md, DATABASES reste sur la connexion 'default').


class VwRentabiliteGlobale(models.Model):
    """Dashboard 1 (Santé Globale). Grain = mois. PK désignée : mois (unique en base, cf.
    dbt_bi/models/marts/aggregates/_aggregates.yml)."""

    mois = models.DateField(primary_key=True)
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    cout_achat = models.DecimalField(max_digits=15, decimal_places=2)
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2)
    marge_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    cout_salaires = models.DecimalField(max_digits=15, decimal_places=2)
    salaires_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    cout_depenses = models.DecimalField(max_digits=15, decimal_places=2)
    depenses_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    rentabilite_nette = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_rentabilite_globale'


class VwRentabiliteProduit(models.Model):
    """Dashboard 2. Grain = produit. PK désignée : produit_id (unique en base)."""

    produit_id = models.IntegerField(primary_key=True)
    produit_nom = models.CharField(max_length=100)
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    cout_achat = models.DecimalField(max_digits=15, decimal_places=2)
    marge = models.DecimalField(max_digits=15, decimal_places=2)
    marge_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    quantite_vendue_kg = models.DecimalField(max_digits=12, decimal_places=2)
    stock_moyen = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    rotation_stock = models.DecimalField(max_digits=8, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_rentabilite_produit'


class VwPerformanceSuperviseur(models.Model):
    """Dashboard 3, partie 1. Grain = superviseur (dim_agent type_agent='entrepot').
    PK désignée : superviseur_id (unique en base)."""

    superviseur_id = models.IntegerField(primary_key=True)
    superviseur_nom = models.CharField(max_length=200)
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2)
    cout_equipe = models.DecimalField(max_digits=15, decimal_places=2)
    rentabilite_nette = models.DecimalField(max_digits=15, decimal_places=2)
    nb_agents_actifs = models.IntegerField()
    ca_moyen_par_agent = models.DecimalField(max_digits=15, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_superviseur'


class VwPerformanceAgent(models.Model):
    """Dashboard 4. Grain = agent (type terrain/agent_gros/agent_polivalent).
    PK désignée : agent_id (unique en base)."""

    STATUT_ATTEINT = "atteint"
    STATUT_PROCHE = "proche"
    STATUT_SOUS_OBJECTIF = "sous_objectif"

    agent_id = models.IntegerField(primary_key=True)
    nom_complet = models.CharField(max_length=200)
    type_agent = models.CharField(max_length=50)
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    jours_actifs = models.IntegerField()
    kg_par_jour = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    statut_objectif_50kg = models.CharField(max_length=20, null=True)
    marge = models.DecimalField(max_digits=15, decimal_places=2)
    incentive = models.DecimalField(max_digits=15, decimal_places=2)
    rentabilite_agent = models.DecimalField(max_digits=15, decimal_places=2)
    ratio_incentive_marge_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_agent'


class VwAnalyseStock(models.Model):
    """Dashboard 5, volet stock. Grain = produit x fournisseur (snapshot courant).
    PK désignée : produit_id — NON unique dans cette vue (grain composite produit x
    fournisseur, jamais testée unique côté dbt, cf. _aggregates.yml). Acceptable pour un
    usage 100% lecture/affichage de liste (ce queryset n'est jamais utilisé avec .get()) ;
    à ne pas réutiliser tel quel si un usage nécessitant l'unicité de la PK apparaît."""

    produit_id = models.IntegerField(primary_key=True)
    produit_nom = models.CharField(max_length=100, null=True)
    fournisseur_id = models.IntegerField(null=True)
    fournisseur_nom = models.CharField(max_length=100, null=True)
    quantite_restante = models.DecimalField(max_digits=12, decimal_places=2)
    valeur_stock = models.DecimalField(max_digits=15, decimal_places=2)
    jours_en_stock_moyen = models.DecimalField(max_digits=6, decimal_places=1, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_analyse_stock'


class VwMargeFournisseur(models.Model):
    """Dashboard 5, volet fournisseur (dbt-2). Grain = fournisseur x mois.
    PK désignée : fournisseur_mois_id (surrogate ajouté dans la vue, cf.
    dbt_bi/models/marts/aggregates/vw_marge_fournisseur.sql — modèle créé par ce sprint,
    pas de contrainte "ne pas renommer" contrairement aux 5 vues historiques)."""

    fournisseur_mois_id = models.IntegerField(primary_key=True)
    fournisseur_id = models.IntegerField()
    fournisseur_nom = models.CharField(max_length=100, null=True)
    mois = models.DateField()
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    cout_achat_systeme = models.DecimalField(max_digits=15, decimal_places=2)
    marge_systeme = models.DecimalField(max_digits=15, decimal_places=2)
    marge_pct_systeme = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    prix_achat_corrige_pondere = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    calibre = models.BooleanField()
    cout_achat_calibre = models.DecimalField(max_digits=15, decimal_places=2)
    marge_calibree = models.DecimalField(max_digits=15, decimal_places=2)
    marge_calibree_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_marge_fournisseur'


class VwDepensesCategorie(models.Model):
    """Dashboard 3, partie 2 (KPI-701/702, 20/07/2026). Grain = catégorie x mois.
    PK désignée : depense_categorie_id (surrogate ajouté dans la vue, modèle créé par ce
    sprint — cf. dbt_bi/models/marts/aggregates/vw_depenses_categorie.sql)."""

    depense_categorie_id = models.IntegerField(primary_key=True)
    mois = models.DateField()
    categorie = models.CharField(max_length=40, null=True)
    montant = models.DecimalField(max_digits=15, decimal_places=2)
    montant_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_depenses_categorie'
