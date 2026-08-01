from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Agent, AffectationLotSuperviseur, DistributionAgent


class Command(BaseCommand):
    help = (
        "Réassigne le superviseur de tous les agents actuellement sous la supervision "
        "d'un agent donné vers un autre agent, ainsi que le stock déjà distribué/affecté "
        "par l'ancien superviseur (DistributionAgent, AffectationLotSuperviseur), pour que "
        "le nouveau superviseur puisse voir et vendre ce stock sans redistribution."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--de",
            default="ismael.diawara",
            help="username de l'agent superviseur actuel (défaut : ismael.diawara)",
        )
        parser.add_argument(
            "--vers",
            default="sidibe.mankoulako",
            help="username du nouvel agent superviseur (défaut : sidibe.mankoulako)",
        )

    def handle(self, *args, **options):
        username_de = options["de"]
        username_vers = options["vers"]

        try:
            ancien_superviseur = Agent.objects.get(user__username=username_de)
        except Agent.DoesNotExist:
            raise CommandError(f"Aucun agent trouvé pour l'utilisateur '{username_de}'.")

        try:
            nouveau_superviseur = Agent.objects.get(user__username=username_vers)
        except Agent.DoesNotExist:
            raise CommandError(f"Aucun agent trouvé pour l'utilisateur '{username_vers}'.")

        agents = Agent.objects.filter(superviseur=ancien_superviseur)
        distributions = DistributionAgent.objects.filter(superviseur=ancien_superviseur)
        affectations = AffectationLotSuperviseur.objects.filter(superviseur=ancien_superviseur)

        nb_agents = agents.count()
        nb_distributions = distributions.count()
        nb_affectations = affectations.count()

        if not (nb_agents or nb_distributions or nb_affectations):
            self.stdout.write(self.style.WARNING(
                f"Rien à réassigner depuis '{username_de}' (aucun agent, distribution ou "
                f"affectation)."
            ))
            return

        with transaction.atomic():
            agents.update(superviseur=nouveau_superviseur)
            distributions.update(superviseur=nouveau_superviseur)
            affectations.update(superviseur=nouveau_superviseur)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Réassigné de '{username_de}' vers '{username_vers}' : "
            f"{nb_agents} agent(s), {nb_distributions} distribution(s), "
            f"{nb_affectations} affectation(s) de lot."
        ))
