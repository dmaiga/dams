from django.conf import settings
from django.db import models

from core.models import LotEntrepot


class AjustementPrixAchat(models.Model):
    """Calibration du prix d'achat fournisseur (dbt-2 ; refonte 23/07/2026, dbt-7). Saisie
    admin Direction uniquement.

    Append-only : pas de suppression ni de modification une fois enregistré (voir
    BiAjustementPrixAchatAdmin) — un ajustement erroné s'annule par un contre-ajustement
    (nouvelle ligne, quantite_concernee négative ou prix corrigé mis à jour).

    Rattaché directement à un LotEntrepot (au lieu de fournisseur/année/mois/produit saisis à
    la main) : fournisseur, produit, année et mois sont dérivés du lot côté dbt
    (dbt_bi/models/staging/stg_ajustements_prix_achat.sql, jointure sur core_lotentrepot) —
    ni dupliqués ni resaisis ici. Un même lot renégocié à plusieurs prix (ex. 150 unités à
    11000 puis 150 à 10000) se saisit en plusieurs lignes distinctes pointant sur le même lot.
    """

    lot = models.ForeignKey(
        LotEntrepot,
        on_delete=models.PROTECT,
        related_name="ajustements_prix_achat",
        verbose_name="Lot",
        help_text="Lot dont le prix d'achat a été renégocié après réception — fournisseur, "
        "produit, année et mois en sont dérivés automatiquement, rien d'autre à ressaisir.",
    )
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
        return f"{self.lot.reference_lot or self.lot_id} — {self.prix_achat_corrige} FCFA"


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
    rentabilite_nette_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_rentabilite_globale'


class VwRentabiliteJournaliere(models.Model):
    """Dashboard 1 (Santé Globale), graphique de tendance uniquement. Grain = jour. PK
    désignée : jour (unique en base). Pas de salaires à ce grain (cf.
    dbt_bi/models/marts/aggregates/vw_rentabilite_journaliere.sql) — ne sert que le graphique
    CA/dépenses/marge brute quand un mois précis est filtré (vw_rentabilite_globale réduirait
    alors la série à un seul point)."""

    jour = models.DateField(primary_key=True)
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    cout_achat = models.DecimalField(max_digits=15, decimal_places=2)
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2)
    cout_depenses = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_rentabilite_journaliere'


class VwRentabiliteProduit(models.Model):
    """Dashboard 2. Grain = produit x mois. PK désignée : produit_mois_id (surrogate ajouté
    dans la vue, cf. dbt_bi/models/marts/aggregates/vw_rentabilite_produit.sql) — un produit
    sans vente sur un mois donné n'a pas de ligne pour ce mois."""

    produit_mois_id = models.IntegerField(primary_key=True)
    produit_id = models.IntegerField()
    produit_nom = models.CharField(max_length=100, null=True)
    mois = models.DateField()
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
    """Dashboard "Performance Agent & Équipes", volet équipes. Grain = superviseur
    (dim_agent type_agent='entrepot') x mois. PK désignée : superviseur_mois_id (surrogate
    ajouté dans la vue, cf. dbt_bi/models/marts/aggregates/vw_performance_superviseur.sql) —
    un superviseur sans vente sur un mois donné a quand même une ligne (valeurs à 0)."""

    superviseur_mois_id = models.IntegerField(primary_key=True)
    superviseur_id = models.IntegerField()
    superviseur_nom = models.CharField(max_length=200)
    mois = models.DateField()
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2)
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    cout_equipe = models.DecimalField(max_digits=15, decimal_places=2)
    rentabilite_nette = models.DecimalField(max_digits=15, decimal_places=2)
    nb_agents_actifs = models.IntegerField()
    ca_moyen_par_agent = models.DecimalField(max_digits=15, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_superviseur'


class VwPerformanceAgent(models.Model):
    """Dashboard "Performance Agent & Équipes". Grain = agent (terrain/agent_gros/
    agent_polivalent) x mois. PK désignée : agent_mois_id (surrogate ajouté dans la vue, cf.
    dbt_bi/models/marts/aggregates/vw_performance_agent.sql) — un agent actif sans vente sur
    un mois donné a quand même une ligne (kg_par_jour=0, statut 'sous_objectif')."""

    STATUT_ATTEINT = "atteint"
    STATUT_PROCHE = "proche"
    STATUT_SOUS_OBJECTIF = "sous_objectif"

    agent_mois_id = models.IntegerField(primary_key=True)
    agent_id = models.IntegerField()
    nom_complet = models.CharField(max_length=200)
    type_agent = models.CharField(max_length=50)
    superviseur_id = models.IntegerField(null=True)
    superviseur_nom = models.CharField(max_length=200, null=True)
    mois = models.DateField()
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    jours_actifs = models.IntegerField()
    jours_ouvres = models.IntegerField(null=True)
    kg_par_jour = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    statut_objectif_50kg = models.CharField(max_length=20, null=True)
    marge = models.DecimalField(max_digits=15, decimal_places=2)
    incentive = models.DecimalField(max_digits=15, decimal_places=2)
    rentabilite_agent = models.DecimalField(max_digits=15, decimal_places=2)
    ratio_incentive_marge_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_agent'


class VwPerformanceSuperviseurSemaine(models.Model):
    """Dashboard "Agents", volet équipes hebdomadaire (24/07/2026, S-702). Miroir hebdomadaire
    (semaine ISO lundi-dimanche) de VwPerformanceSuperviseur — pas de cout_equipe/
    rentabilite_nette/ca_moyen_par_agent ici, cf.
    dbt_bi/models/marts/aggregates/vw_performance_superviseur_semaine.sql."""

    superviseur_semaine_id = models.IntegerField(primary_key=True)
    superviseur_id = models.IntegerField()
    superviseur_nom = models.CharField(max_length=200)
    semaine = models.DateField()
    ca = models.DecimalField(max_digits=15, decimal_places=2)
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2)
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    nb_agents_actifs = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_superviseur_semaine'


class VwPerformanceAgentSemaine(models.Model):
    """Dashboard "Agents", volet hebdomadaire (24/07/2026, S-702). Miroir hebdomadaire (semaine
    ISO lundi-dimanche) de VwPerformanceAgent — pas d'incentive/ratio ici (fct_salaires est
    mensuel), cf. dbt_bi/models/marts/aggregates/vw_performance_agent_semaine.sql."""

    agent_semaine_id = models.IntegerField(primary_key=True)
    agent_id = models.IntegerField()
    nom_complet = models.CharField(max_length=200)
    type_agent = models.CharField(max_length=50)
    superviseur_id = models.IntegerField(null=True)
    superviseur_nom = models.CharField(max_length=200, null=True)
    semaine = models.DateField()
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    jours_actifs = models.IntegerField()
    jours_ouvres = models.IntegerField(null=True)
    kg_par_jour = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    statut_objectif_50kg = models.CharField(max_length=20, null=True)
    marge = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'bi_"."vw_performance_agent_semaine'


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
    """Dashboard 5, volet fournisseur (dbt-2 ; produit ajouté le 23/07/2026). Grain =
    fournisseur x produit x mois. PK désignée : fournisseur_mois_id (surrogate ajouté dans la
    vue, cf. dbt_bi/models/marts/aggregates/vw_marge_fournisseur.sql — modèle créé par ce
    sprint, pas de contrainte "ne pas renommer" contrairement aux 5 vues historiques)."""

    fournisseur_mois_id = models.IntegerField(primary_key=True)
    fournisseur_id = models.IntegerField()
    fournisseur_nom = models.CharField(max_length=100, null=True)
    produit_id = models.IntegerField(null=True)
    produit_nom = models.CharField(max_length=100, null=True)
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


class FctStockAgent(models.Model):
    """Sprint-11 (18/08/2026). Fiche détail agent, bloc "Stock en main". Grain = 1 ligne par
    DetailDistribution encore active (stock restant > 0) — un agent qui a tout vendu/perdu sur
    une ligne n'y apparaît plus. Batch (pas temps réel, décision produit), cf.
    dbt_bi/models/marts/fct_stock_agent.sql."""

    stock_agent_id = models.IntegerField(primary_key=True)
    detail_distribution_id = models.IntegerField()
    agent_id = models.IntegerField()
    superviseur_id = models.IntegerField(null=True)
    lot_id = models.IntegerField()
    produit_id = models.IntegerField(null=True)
    produit_nom = models.CharField(max_length=100, null=True)
    date_reception = models.DateField(null=True)
    stock_restant = models.DecimalField(max_digits=12, decimal_places=2)
    stock_restant_kg = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'bi_"."fct_stock_agent'


class VwVentesAgentProduit(models.Model):
    """Sprint-11 (18/08/2026). Fiche détail agent, bloc "Produits vendus". Grain = agent x
    produit x mois — kg_vendus net des pertes (cohérent avec VwPerformanceAgent). "Type" de
    produit = nom du produit (pas de vraie catégorie sur Produit), cf.
    dbt_bi/models/marts/aggregates/vw_ventes_agent_produit.sql."""

    ventes_agent_produit_id = models.IntegerField(primary_key=True)
    agent_id = models.IntegerField()
    produit_id = models.IntegerField(null=True)
    produit_nom = models.CharField(max_length=100, null=True)
    mois = models.DateField()
    kg_vendus = models.DecimalField(max_digits=12, decimal_places=2)
    ca_total = models.DecimalField(max_digits=15, decimal_places=2)
    marge = models.DecimalField(max_digits=15, decimal_places=2)
    nombre_ventes = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'bi_"."vw_ventes_agent_produit'
