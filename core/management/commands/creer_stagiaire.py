from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Agent
from django.utils import timezone
from datetime import timedelta
import unicodedata

class Command(BaseCommand):
    help = 'Crée un nouvel agent stagiaire avec génération automatique du username'

    def add_arguments(self, parser):
        parser.add_argument(
            '--first_name',
            type=str,
            required=True,
            help='Prénom du stagiaire'
        )
        parser.add_argument(
            '--last_name',
            type=str,
            required=True,
            help='Nom du stagiaire'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='temp123',
            help='Mot de passe du stagiaire (défaut: stagiaire123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email du stagiaire',
            default='non-email@email.com'
        )
        parser.add_argument(
            '--telephone',
            type=str,
            help='Numéro de téléphone'
        )
        parser.add_argument(
            '--duree_jours',
            type=int,
            default=14,
            help='Durée du stage en jours (défaut: 14)'
        )
        parser.add_argument(
            '--date-debut',
            type=str,
            help='Date de début du stage (format: JJ/MM/AAAA) - défaut: maintenant'
        )

    def normalize_name(self, name):
        """Normalise un nom pour le username"""
        # Supprimer les accents
        name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
        # Remplacer les espaces par des points et mettre en minuscule
        return name.lower().replace(' ', '.')

    def generate_username(self, first_name, last_name):
        """Génère un username unique au format prenom.nom"""
        base_username = f"{self.normalize_name(first_name)}.{self.normalize_name(last_name)}"
        username = base_username
        counter = 1
        
        # Vérifier les doublons et ajouter +1 si nécessaire
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
            
        return username

    def handle(self, *args, **options):
        try:
            first_name = options['first_name']
            last_name = options['last_name']
            
            # Générer le username automatiquement
            username = self.generate_username(first_name, last_name)
            
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                password=options['password'],
                email=options.get('email', ''),
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )

            # Calculer les dates
            if options.get('date_debut'):
                date_mise_service = timezone.datetime.strptime(
                    options['date_debut'], '%d/%m/%Y'
                ).replace(tzinfo=timezone.get_current_timezone())
            else:
                date_mise_service = timezone.now()

            date_expiration = date_mise_service + timedelta(days=options['duree_jours'])

            # Créer l'agent stagiaire
            agent = Agent.objects.create(
                user=user,
                type_agent='stagiaire',
                telephone=options.get('telephone', ''),
                date_mise_service=date_mise_service,
                date_expiration=date_expiration
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Stagiaire créé avec succès!\n"
                    f"• Nom: {agent.full_name}\n"
                    f"• Username généré: {user.username}\n"
                    f"• Mot de passe: {options['password']}\n"
                    f"• Date début: {date_mise_service.strftime('%d/%m/%Y')}\n"
                    f"• Date expiration: {date_expiration.strftime('%d/%m/%Y')}\n"
                    f"• Jours restants: {agent.jours_restants}\n"
                    f"• Statut: {agent.statut_stagiaire}"
                )
            )

        except Exception as e:
            raise CommandError(f"Erreur lors de la création: {str(e)}")