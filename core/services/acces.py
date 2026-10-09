"""Accès par groupe Django (au-delà du type d'agent)."""

# Suivi du stock détenu par les agents de vente (onglet « Suivi stock agents »).
# Le gestionnaire de stock (type_agent='gestionnaire_stock') y a toujours accès ;
# le groupe y ajoute des personnes d'autres rôles (ex. jeanclaude.sup).
GROUPE_SUIVI_STOCK_AGENTS = "Suivi stock agents"


def peut_suivre_stock_agents(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    agent = getattr(user, 'agent', None)
    if agent is not None and agent.est_gestionnaire_stock:
        return True
    return user.groups.filter(name=GROUPE_SUIVI_STOCK_AGENTS).exists()
