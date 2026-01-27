from django.core.management.base import BaseCommand
from core.models import Agent


class Command(BaseCommand):
    """
    Affectation des agents aux superviseurs selon la stratégie :
    1) Abdoulaye = superviseur par défaut
    2) Sidibe = override ciblé sur terrain actif
    """

    help = "Affecte les agents aux superviseurs (fallback Abdoulaye, override Sidibe)"

    def handle(self, *args, **options):

        # ====================================================
        # RÉCUPÉRATION DES SUPERVISEURS
        # ====================================================
        sup_abdoulaye = Agent.objects.get(
            user__username="abdoulaye.kone",
            type_agent="entrepot"
        )

        sup_sidibe = Agent.objects.get(
            user__username="sidibe.mankoulako",
            type_agent="entrepot"
        )

        # ====================================================
        # 1️⃣ AFFECTATION PAR DÉFAUT → ABDOULAYE
        # ----------------------------------------------------
        # Tous les agents terrain, agent_gros, stagiaires
        # (actifs OU inactifs)
        # ====================================================
        default_count = Agent.objects.filter(
            type_agent__in=["terrain", "agent_gros", "stagiaire"]
        ).update(superviseur=sup_abdoulaye)

        # ====================================================
        # 2️⃣ OVERRIDE → SIDIBE
        # ----------------------------------------------------
        # Uniquement les agents terrain ACTIFS
        # Cette étape écrase l'affectation précédente
        # ====================================================
        override_count = Agent.objects.filter(
            type_agent="terrain",
            est_actif=True
        ).update(superviseur=sup_sidibe)

        # ====================================================
        # LOG FINAL
        # ====================================================
        self.stdout.write(self.style.SUCCESS(
            "✅ Affectation terminée\n"
            f"   • Affectation par défaut → Abdoulaye : {default_count}\n"
            f"   • Override terrain actifs → Sidibe : {override_count}"
        ))
