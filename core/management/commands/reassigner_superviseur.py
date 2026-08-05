from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Agent, AffectationLotSuperviseur, DistributionAgent


class Command(BaseCommand):
    help = (
        "Réassigne le superviseur d'un agent donné vers un autre. Par défaut, "
        "transfère TOUS les agents sous la supervision de l'ancien superviseur, ainsi "
        "que le stock déjà distribué/affecté par ce superviseur (DistributionAgent, "
        "AffectationLotSuperviseur). Avec --agents, ne transfère que les agents de "
        "terrain listés (et les distributions qu'ils ont reçues), sans toucher aux "
        "affectations de lot qui restent rattachées au superviseur dans son ensemble."
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
        parser.add_argument(
            "--agents",
            default=None,
            help=(
                "Liste de usernames d'agents de terrain à transférer, séparés par des "
                "virgules (ex: --agents traore.moussa,keita.awa). Si omis, transfère "
                "tous les agents sous l'ancien superviseur (comportement historique)."
            ),
        )

    def handle(self, *args, **options):
        username_de = options["de"]
        username_vers = options["vers"]
        agents_bruts = options["agents"]

        try:
            ancien_superviseur = Agent.objects.get(user__username=username_de)
        except Agent.DoesNotExist:
            raise CommandError(f"Aucun agent trouvé pour l'utilisateur '{username_de}'.")

        try:
            nouveau_superviseur = Agent.objects.get(user__username=username_vers)
        except Agent.DoesNotExist:
            raise CommandError(f"Aucun agent trouvé pour l'utilisateur '{username_vers}'.")

        if agents_bruts:
            self._reassigner_agents_specifiques(
                agents_bruts, ancien_superviseur, nouveau_superviseur,
                username_de, username_vers,
            )
        else:
            self._reassigner_tout(ancien_superviseur, nouveau_superviseur, username_de, username_vers)

    def _reassigner_agents_specifiques(self, agents_bruts, ancien_superviseur, nouveau_superviseur,
                                        username_de, username_vers):
        usernames = [u.strip() for u in agents_bruts.split(",") if u.strip()]
        if not usernames:
            raise CommandError("--agents ne contient aucun username valide.")

        agents = Agent.objects.filter(
            superviseur=ancien_superviseur, user__username__in=usernames
        )

        trouves = set(agents.values_list("user__username", flat=True))
        manquants = set(usernames) - trouves
        if manquants:
            raise CommandError(
                f"Agent(s) introuvable(s) sous '{username_de}' : {', '.join(sorted(manquants))}."
            )

        # ⚠️ Capturer les PK des agents AVANT toute mise à jour : si on filtre
        # distributions via `agent_terrain__in=agents` (queryset paresseux),
        # la sous-requête est ré-évaluée au moment du .update() sur
        # distributions, donc APRÈS que agents.update() ait déjà changé leur
        # superviseur — la sous-requête ne matche alors plus rien et
        # distributions.update() ne touche silencieusement aucune ligne.
        agent_ids = list(agents.values_list("pk", flat=True))

        distributions = DistributionAgent.objects.filter(
            superviseur=ancien_superviseur, agent_terrain_id__in=agent_ids
        )

        nb_agents = len(agent_ids)
        nb_distributions = distributions.count()

        with transaction.atomic():
            agents.update(superviseur=nouveau_superviseur)
            distributions.update(superviseur=nouveau_superviseur)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Réassigné {nb_agents} agent(s) ({', '.join(sorted(trouves))}) de "
            f"'{username_de}' vers '{username_vers}' : {nb_distributions} distribution(s)."
        ))

    def _reassigner_tout(self, ancien_superviseur, nouveau_superviseur, username_de, username_vers):
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
