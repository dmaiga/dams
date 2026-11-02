"""Recherche d'un agent par son nom (barre de recherche de direction)."""
from django.db.models import Q


def filtre_nom_agent(prefixe_user, terme):
    """Q sur prénom / nom / identifiant du user situé à `prefixe_user` (ex. "agent__user").

    Chaque mot du terme doit correspondre à l'un des trois champs, dans n'importe quel ordre :
    « moussa traoré » et « traoré moussa » trouvent le même agent.
    """
    condition = Q()
    for mot in (terme or "").split():
        condition &= (
            Q(**{f"{prefixe_user}__first_name__icontains": mot})
            | Q(**{f"{prefixe_user}__last_name__icontains": mot})
            | Q(**{f"{prefixe_user}__username__icontains": mot})
        )
    return condition
