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


# Vérificateur général : consultation (lecture) des écrans direction suivants — Tableau de bord,
# Agents, Produits, Suivi des Distributions, Fournisseurs, Ventes, Analyse Opérationnelle,
# Surveillance, BI. Rémunération, Finance, Champs et Admin lui sont fermés (menu masqué + accès
# bloqué sur Rémunération). Créé par la migration core.0133.
GROUPE_VERIFICATEUR_GENERAL = "Vérificateur général"


def est_verificateur_general(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return user.groups.filter(name=GROUPE_VERIFICATEUR_GENERAL).exists()


def est_verificateur_restreint(user):
    """Membre du groupe : menu restreint, même s'il est aussi agent direction.
    Seuls mdmaiga et les superusers gardent le menu complet."""
    if not est_verificateur_general(user):
        return False
    return not (user.is_superuser or user.username == "mdmaiga")


def peut_consulter_direction(user):
    """Direction (agent), superuser ou vérificateur général."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    agent = getattr(user, 'agent', None)
    if agent is not None and agent.est_direction:
        return True
    return est_verificateur_general(user)
