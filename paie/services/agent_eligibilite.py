from django.db.models import Q

from core.models import Agent

TYPES_AGENTS_PAIE = ["terrain", "agent_gros", "entrepot"]


def agents_eligibles_periode(date_debut, date_fin, type_agent_filter=""):
    """Agents actifs (est_actif=True), plus les agents désactivés dont la fenêtre d'emploi
    connue (date_debut_fonction -> date_fin_contrat) chevauche [date_debut, date_fin].

    Correction du 05/08/2026 : date_fin_contrat est renseignée à la création (contrat
    "prestation" -> +1 mois par défaut, cf. Agent.save()) puis n'est plus jamais mise à jour
    dans l'usage réel — un agent toujours en poste se retrouvait exclu dès que cette date
    dépassait, alors que est_actif=True. est_actif est la source de vérité du statut courant ;
    les dates de contrat ne servent plus qu'au rattrapage d'un agent désactivé depuis, pour les
    mois où il était encore en poste (cas où ni date n'est renseignée -> pas de rattrapage
    possible, l'agent désactivé reste exclu).
    """
    chevauche_periode_connue = (
        Q(date_debut_fonction__isnull=False) | Q(date_fin_contrat__isnull=False)
    ) & (
        Q(date_debut_fonction__isnull=True) | Q(date_debut_fonction__lte=date_fin)
    ) & (Q(date_fin_contrat__isnull=True) | Q(date_fin_contrat__gte=date_debut))

    agents = Agent.objects.filter(type_agent__in=TYPES_AGENTS_PAIE).filter(
        Q(est_actif=True) | chevauche_periode_connue
    )

    if type_agent_filter:
        agents = agents.filter(type_agent=type_agent_filter)

    return agents
