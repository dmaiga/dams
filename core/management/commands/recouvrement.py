from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from core.models import Agent, Recouvrement
from datetime import datetime

class Command(BaseCommand):
    help = 'Créer des recouvrements multiples pour Abdoulaye Kone'

    def add_arguments(self, parser):
        parser.add_argument(
            'agent_username',
            type=str,
            help='Nom d\'utilisateur de l\'agent terrain'
        )
        parser.add_argument(
            '--dates',
            type=str,
            required=True,
            help='Dates (YYYY-MM-DD,YYYY-MM-DD,...)'
        )
        parser.add_argument(
            '--montants', 
            type=str,
            required=True,
            help='Montants (15000,20000,...)'
        )
        parser.add_argument(
            '--superviseur',
            type=str,
            default='abdoulaye.kone',
            help='Nom d\'utilisateur du superviseur (défaut: abdoulaye.kone)'
        )

    def handle(self, *args, **options):
        # Récupérer le superviseur
        try:
            user_superviseur = User.objects.get(username=options['superviseur'])
            superviseur = Agent.objects.get(user=user_superviseur, type_agent='entrepot')
            self.stdout.write(f"Superviseur: {superviseur.full_name}")
        except (User.DoesNotExist, Agent.DoesNotExist):
            self.stderr.write(self.style.ERROR(f"Superviseur {options['superviseur']} non trouvé"))
            return

        # Récupérer l'agent terrain
        try:
            user_agent = User.objects.get(username=options['agent_username'])
            agent_terrain = Agent.objects.get(user=user_agent, type_agent='terrain')
            self.stdout.write(f"Agent terrain: {agent_terrain.full_name}")
        except (User.DoesNotExist, Agent.DoesNotExist):
            self.stderr.write(self.style.ERROR(f"Agent terrain {options['agent_username']} non trouvé"))
            return

        # Validation des données
        dates_list = [d.strip() for d in options['dates'].split(',')]
        montants_list = [m.strip() for m in options['montants'].split(',')]
        
        if len(dates_list) != len(montants_list):
            self.stderr.write(self.style.ERROR("Même nombre de dates et montants requis"))
            return

        # Création des recouvrements
        succes = 0
        echecs = 0
        
        for i, (date_str, montant_str) in enumerate(zip(dates_list, montants_list)):
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                montant = float(montant_str)
                
                recouvrement = Recouvrement(
                    agent=agent_terrain,
                    superviseur=superviseur,
                    montant_recouvre=montant,
                    commentaire='',
                    date_recouvrement=timezone.make_aware(
                        datetime.combine(date_obj, datetime.min.time())
                    )
                )
                recouvrement.full_clean()  # Validation
                recouvrement.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{i+1}. {date_str} - {montant:,.0f} FCFA ✓"
                    )
                )
                succes += 1
                
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(
                        f"{i+1}. {date_str} - {montant_str} FCFA ✗ Erreur: {e}"
                    )
                )
                echecs += 1

        # Résumé final
        self.stdout.write("\n" + "="*50)
        if succes > 0:
            self.stdout.write(self.style.SUCCESS(
                f"SUCCÈS: {succes} recouvrement(s) créé(s)"
            ))
        if echecs > 0:
            self.stdout.write(self.style.WARNING(
                f"ÉCHECS: {echecs} recouvrement(s) non créé(s)"
            ))