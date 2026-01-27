from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    """
    Reset complet de l'environnement DEV après un restore de la base PROD.

    Cette commande rejoue automatiquement toutes les étapes métier nécessaires
    pour remettre la base DEV dans un état cohérent et testable :
    - clôtures comptables
    - initialisation des référentiels
    - migration des rôles
    - sécurisation des accès
    - réaffectations
    - migrations financières
    """

    help = "Reset complet des données DEV après restore PROD"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Démarrage reset DEV")

        # =====================================================
        # 1️⃣ CLÔTURE COMPTABLE ANNUELLE (HISTORIQUE)
        # -----------------------------------------------------
        # Rejoue toutes les clôtures mensuelles sur l'année 2025
        # afin de :
        # - chaîner correctement les soldes
        # - figer l'historique financier
        # - éviter toute incohérence sur les KPIs
        # =====================================================
        call_command(
            "cloturer_mois",
            start="2025-01",
            end="2025-12"
        )

        # =====================================================
        # 2️⃣ INITIALISATION DES RÉFÉRENTIELS PRODUITS
        # -----------------------------------------------------
        # Renseigne les poids unitaires (kg) pour les produits
        # conditionnés afin de garantir :
        # - des calculs physiques cohérents
        # - une analyse correcte des ventes en kg
        # =====================================================
        call_command("init_poids_unitaire")

        # =====================================================
        # 3️⃣ INITIALISATION DES RÈGLES MÉTIER (SALAIRES / INCENTIVES)
        # -----------------------------------------------------
        # Met en place les règles de rémunération :
        # - dotation superviseurs
        # - incentive par kg (terrain)
        # - incentive par carton (agent gros)
        # =====================================================
        call_command("init_regles_remuneration")

        # =====================================================
        # 4️⃣ INITIALISATION DES SALAIRES DE BASE
        # -----------------------------------------------------
        # Affecte les salaires de base selon le type d'agent
        # (terrain, entrepot, agent_gros, etc.)
        # =====================================================
        call_command("init_salaires_agents")

        # =====================================================
        # 5️⃣ MIGRATION DES RÔLES AGENTS (HISTORIQUE & SÉCURITÉ)
        # -----------------------------------------------------
        # - désactive les anciens accès
        # - conserve l'historique comptable
        # - crée les nouveaux agents opérationnels
        # =====================================================
        call_command("migration_roles_agents")

        # =====================================================
        # 6️⃣ RÉAFFECTATION DES AGENTS AUX SUPERVISEURS
        # -----------------------------------------------------
        # Met à jour la hiérarchie :
        # - agents terrain → superviseur actif
        # - agents gros / anciens → superviseur historique
        # =====================================================
        call_command("affecter_superviseurs")
        call_command(
            "migrer_versements_depenses_rot",
            date_bascule="2026-01-01",
            ancien_superviseur="abdoulaye.kone",
            rot="kone.abdoulaye"
        )
        call_command("transferer_recouvrements")

        # =====================================================
        # 7️⃣ MIGRATION FINANCIÈRE (VERSEMENTS & DÉPENSES)
        # -----------------------------------------------------
        # Transfère la responsabilité des flux financiers
        # vers le nouvel agent ROT à partir de la date de bascule
        # =====================================================
      


        # =====================================================
        # FIN DU RESET
        # =====================================================
        self.stdout.write(self.style.SUCCESS("🎉 Reset DEV terminé avec succès"))
