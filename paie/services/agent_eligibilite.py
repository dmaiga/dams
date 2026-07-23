from django.db.models import Q

from core.models import Agent

TYPES_AGENTS_PAIE = ["terrain", "agent_gros", "entrepot"]


def agents_eligibles_periode(date_debut, date_fin, type_agent_filter=""):
    """Agents dont la fenêtre d'emploi (date_debut_fonction -> date_fin_contrat) chevauche
    [date_debut, date_fin], indépendamment de leur est_actif actuel.

    Correction du 23/07/2026 : SalaireGenerationService et SalaireListeService filtraient tous
    les deux sur est_actif=True (statut au moment de l'appel), ce qui excluait à tort un agent
    désactivé depuis lors du calcul de ses salaires pour des mois où il était pourtant bien en
    poste — problème invisible tant que la génération se faisait mois par mois juste après
    (l'agent était encore actif à ce moment-là), mais faussant tout rattrapage historique.

    Repli sur est_actif=True uniquement quand ni date_debut_fonction ni date_fin_contrat ne sont
    renseignées : sans ces dates, impossible de déterminer la fenêtre réelle d'emploi, donc on
    ne peut se fier qu'au statut courant (comportement identique à l'ancien filtre pour ces cas).
    """
    chevauche_periode = (
        Q(date_debut_fonction__isnull=True) | Q(date_debut_fonction__lte=date_fin)
    ) & (Q(date_fin_contrat__isnull=True) | Q(date_fin_contrat__gte=date_debut))
    dates_connues = Q(date_debut_fonction__isnull=False) | Q(date_fin_contrat__isnull=False)

    agents = Agent.objects.filter(type_agent__in=TYPES_AGENTS_PAIE).filter(
        chevauche_periode
    ).filter(dates_connues | Q(est_actif=True))

    if type_agent_filter:
        agents = agents.filter(type_agent=type_agent_filter)

    return agents
