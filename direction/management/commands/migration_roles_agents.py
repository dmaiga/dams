from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import Agent
from decimal import Decimal


class Command(BaseCommand):
    help = "Migration sécurisée des rôles agents avec conservation de l’historique"

    def handle(self, *args, **options):

        with transaction.atomic():

            # ====================================================
            # 1️⃣ SÉCURISATION DES ANCIENS AGENTS (ACCÈS BLOQUÉ)
            # ====================================================

            # Sidibe ancien (terrain -> agent_gros historique)
            sidibe_old = Agent.objects.get(
                user__username="mankoulako.sidibe",
                type_agent="terrain"
            )
            sidibe_old.type_agent = "agent_gros"
            sidibe_old.telephone = "10000001"
            
            sidibe_old.save()

            # Abdoulaye ancien (entrepot historique)
            abdoulaye_old = Agent.objects.get(
                user__username="abdoulaye.kone",
                type_agent="entrepot"
            )
            abdoulaye_old.telephone = "10000002" 
            abdoulaye_old.save()
            # --- Sokona Coulibaly (ancien terrain → gros historique)
            sokona = Agent.objects.get(
                user__username="sokona.coulibaly",
                type_agent="terrain"
            )
            sokona.type_agent = "agent_gros"
            sokona.save()

            # --- Aminata Diakité (ancien terrain → gros historique)
            aminata = Agent.objects.get(
                user__username="aminata.diakite",
                type_agent="terrain"
            )
            aminata.type_agent = "agent_gros"
            aminata.save()

            # --- Safiatou Coulibaly (cas particulier)
            # Pas de changement de rôle, mais ajustement salarial
            safiatou = Agent.objects.get(
                user__username="safiatou.coulibaly",
                type_agent="terrain"
            )
            safiatou.salaire_base_personnel = Decimal("30000")
            safiatou.save()


            self.stdout.write("🔒 Anciens agents sécurisés")

            # ====================================================
            # 2️⃣ CRÉATION DES NOUVEAUX USERS
            # ====================================================

            sidibe_user, _ = User.objects.get_or_create(
                username="sidibe.mankoulako",
                defaults={"is_active": True}
            )

            abdoulaye_user, _ = User.objects.get_or_create(
                username="kone.abdoulaye",
                defaults={"is_active": True}
            )

            # ====================================================
            # 3️⃣ CRÉATION DES NOUVEAUX AGENTS OPÉRATIONNELS
            # ====================================================

            Agent.objects.get_or_create(
                user=sidibe_user,
                defaults={
                    "type_agent": "entrepot",
                    "telephone": "74105503",
                    "est_actif": True,
                    "salaire_base_personnel": Decimal("85000"),
                }
            )

            Agent.objects.get_or_create(
                user=abdoulaye_user,
                defaults={
                    "type_agent": "rot",
                    "telephone": "72014965",
                    "est_actif": True,
                    "salaire_base_personnel": Decimal("0.0"),
                    
                }
            )

            self.stdout.write(self.style.SUCCESS(
                "✅ Nouveaux agents créés (entrepot & rot)"
            ))

        self.stdout.write(self.style.SUCCESS("🎉 Migration des rôles terminée avec succès"))
