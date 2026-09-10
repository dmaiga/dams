from django.core.management.base import BaseCommand

from core.models import Agent, SnapshotSuperviseurAgent


class Command(BaseCommand):
    """
    Capture manuelle de l'état courant `agent -> superviseur` dans
    SnapshotSuperviseurAgent. À lancer avant/après une réaffectation dont on
    veut garder une trace ponctuelle — pas d'automatisation, pas de lecture
    dans les rapports (voir core/APP_CORE.md §10).
    """

    help = "Sauvegarde un instantané de la hiérarchie agent -> superviseur actuelle."

    def handle(self, *args, **options):
        agents = Agent.objects.exclude(type_agent='direction')

        snapshots = [
            SnapshotSuperviseurAgent(agent=agent, superviseur=agent.superviseur)
            for agent in agents
        ]
        SnapshotSuperviseurAgent.objects.bulk_create(snapshots)

        self.stdout.write(self.style.SUCCESS(
            f"Snapshot enregistré : {len(snapshots)} agent(s)."
        ))
