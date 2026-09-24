from collections import defaultdict

from core.models import RecouvrementSuperviseur
from core.templatetags.format_fcfa import fcfa
from finance.services import lister_soldes_superviseurs, solde_superviseur
from monitoring.constants import DESCRIPTIONS_ALERTES
from monitoring.providers.telegram import TelegramProvider
from monitoring.services.deduplication_service import AlerteDeduplicationService
from surveillance.services.prix_service import PrixSurveillanceService
from surveillance.services.stock_age_service import StockAgeService


def _fmt_date(valeur):
    return valeur.strftime('%d/%m/%Y') if valeur else '—'


def _ligne_stock(p):
    """Rendu d'une ligne produit de stock dormant, identique pour les blocs
    « superviseur » et « agent » (demande mdmaiga 08/09/2026 : même niveau de
    détail que la commande `agents_stock_dormant` — produit, quantité restante,
    date de réception, ancienneté)."""
    return (
        f"• {p['produit'].nom} — reste {p['quantite_restante']} — "
        f"reçu le {_fmt_date(p['date_reference'])} — {p['jours_ecoules']} j"
    )


def _grouper_par_superviseur(items, cle_superviseur='superviseur'):
    """Retourne (groupes, sans_superviseur) : groupes est un dict {superviseur:
    [items]} qui préserve l'ordre d'apparition, sans_superviseur la liste des
    items dont cle_superviseur est None (rattachement non défini)."""
    groupes = defaultdict(list)
    sans_superviseur = []
    for item in items:
        superviseur = item.get(cle_superviseur)
        if superviseur is None:
            sans_superviseur.append(item)
        else:
            groupes[superviseur].append(item)
    return groupes, sans_superviseur


class AlerteMoteur:
    """Évalue les alertes MVP de surveillance et diffuse, par thématique, un
    message Telegram unique et regroupé (refonte du 2026-08-13) — plutôt
    qu'un message par situation individuelle (agent, lot, superviseur).

    Lecture seule sur finance/surveillance — écriture uniquement sur Alerte
    (core), via AlerteDeduplicationService. Aucun signal, aucune vue.

    Convention de déduplication pour les messages agrégés : chaque règle ne
    crée jamais qu'une seule Alerte ACTIVE par type_alerte (aucune clé
    d'identification passée à get_ou_creer) — cloturer_si_resolue reçoit donc
    [{}] tant qu'il y a quelque chose à signaler, [] sinon, pour
    créer/rafraîchir ou résoudre cette Alerte unique.
    """

    # ------------------------------------------------------------------
    # Soldes superviseurs — un seul message listant tous les superviseurs
    # en alerte (le calcul du solde lui-même, finance.services, est inchangé).
    # ------------------------------------------------------------------

    @staticmethod
    def evaluer_solde_superviseur():
        situations_solde = []
        superviseurs_persistants = []

        for item in lister_soldes_superviseurs():
            superviseur = item["superviseur"]

            if item["alerte"]:
                situations_solde.append(item)

            # "solde_persistant" reste une alerte individuelle par superviseur
            # (règle critique distincte, hors périmètre du regroupement
            # demandé).
            derniers_cycles = list(
                RecouvrementSuperviseur.objects
                .filter(superviseur=superviseur)
                .order_by("-date_recouvrement")[:3]
            )
            trois_cycles_residuels = len(derniers_cycles) == 3 and all(
                solde_superviseur(superviseur, date_fin=cycle.date_recouvrement.date())["solde"] > 0
                for cycle in derniers_cycles
            )
            if trois_cycles_residuels:
                superviseurs_persistants.append({"superviseur": superviseur.user})
                alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                    type_alerte="solde_persistant",
                    defaults={
                        "niveau": "critique",
                        "message": (
                            f"⚠️ SOLDE PERSISTANT — {superviseur.full_name}\n"
                            f"{DESCRIPTIONS_ALERTES['solde_persistant']}\n\n"
                            f"Encore débiteur après 3 cycles de remise consécutifs."
                        ),
                    },
                    superviseur=superviseur.user,
                )
                if doit_envoyer:
                    TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("solde_persistant", superviseurs_persistants)

        if situations_solde:
            lignes = "\n".join(
                f"• {item['superviseur'].full_name} : {fcfa(item['solde'])} FCFA"
                for item in situations_solde
            )
            message = f"⚠️ SOLDES SUPERVISEURS\n{DESCRIPTIONS_ALERTES['solde']}\n\n{lignes}"
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="solde",
                defaults={"niveau": "info", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("solde", [{}] if situations_solde else [])

    # ------------------------------------------------------------------
    # Stock ancien — trois messages distincts (entrepôt / superviseurs /
    # agents), chacun avec son propre seuil (StockAgeService).
    # ------------------------------------------------------------------

    @staticmethod
    def evaluer_stock_ancien():
        entrepot, superviseurs, agents = [], [], []
        for ligne in StockAgeService.lots_stock_dormant():
            if ligne["origine"] == "entrepot":
                entrepot.append(ligne)
            elif ligne["origine"] == "superviseur":
                superviseurs.append(ligne)
            else:
                agents.append(ligne)

        AlerteMoteur._envoyer_stock_entrepot(entrepot)
        AlerteMoteur._envoyer_stock_superviseurs(superviseurs)
        AlerteMoteur._envoyer_stock_agents(agents)

    @staticmethod
    def _envoyer_stock_entrepot(lignes):
        if lignes:
            corps = "\n\n".join(
                f"• {ligne['produit'].nom}\n  reçu le {_fmt_date(ligne['date_reference'])}\n  {ligne['jours_ecoules']} jours"
                for ligne in lignes
            )
            message = f"⚠️ STOCK DORMANT — ENTREPÔT\n{DESCRIPTIONS_ALERTES['stock_entrepot']}\n\n{corps}"
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_entrepot",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("stock_entrepot", [{}] if lignes else [])

    @staticmethod
    def _envoyer_stock_superviseurs(lignes):
        # Un message Telegram distinct par superviseur (refonte du 24/09/2026, à la demande
        # de mdmaiga — auparavant un seul message combinant tous les superviseurs), pour que
        # chacun ne reçoive que ses propres produits en rétention. Une AffectationLotSuperviseur
        # porte toujours un superviseur (FK non nullable) : _sans_superviseur est ici toujours
        # vide, ignoré.
        groupes, _sans_superviseur = _grouper_par_superviseur(lignes)

        for superviseur, produits in groupes.items():
            lignes_produits = "\n".join(_ligne_stock(p) for p in produits)
            message = (
                f"⚠️ STOCK EN RÉTENTION — {superviseur.full_name}\n"
                f"{DESCRIPTIONS_ALERTES['stock_superviseur']}\n\n{lignes_produits}"
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_superviseur",
                defaults={"niveau": "warning", "message": message},
                superviseur=superviseur.user,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue(
            "stock_superviseur", [{"superviseur": s.user} for s in groupes.keys()]
        )

    @staticmethod
    def _envoyer_stock_agents(lignes):
        # Même logique que _envoyer_stock_superviseurs (24/09/2026) : un message par
        # superviseur, listant ses propres agents. Un agent de vente sans superviseur
        # assigné ne devrait pas exister en pratique (Constat 9) ; s'il se présente, ses
        # lignes de stock sont simplement ignorées ici plutôt que rattachées à un
        # superviseur inventé — elles restent visibles depuis le dashboard surveillance.
        groupes, _sans_superviseur = _grouper_par_superviseur(lignes)

        for superviseur, produits_agents in groupes.items():
            par_agent = defaultdict(list)
            for p in produits_agents:
                par_agent[p["agent"]].append(p)
            sous_blocs = []
            for agent, produits in par_agent.items():
                lignes_produits = "\n".join(_ligne_stock(p) for p in produits)
                sous_blocs.append(f"{agent.full_name}\n{lignes_produits}")
            message = (
                f"⚠️ STOCK CHEZ LES AGENTS — {superviseur.full_name}\n"
                f"{DESCRIPTIONS_ALERTES['stock_agent']}\n\n" + "\n\n".join(sous_blocs)
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_agent",
                defaults={"niveau": "warning", "message": message},
                superviseur=superviseur.user,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue(
            "stock_agent", [{"superviseur": s.user} for s in groupes.keys()]
        )

    # ------------------------------------------------------------------
    # Ventes sous la marge minimale — un seul message, groupé par
    # superviseur puis par agent. La vente est la référence (pas le lot).
    # ------------------------------------------------------------------

    @staticmethod
    def evaluer_variation_prix():
        situations = PrixSurveillanceService.ventes_sous_marge_minimale()
        groupes, sans_superviseur = _grouper_par_superviseur(situations)

        if groupes or sans_superviseur:
            blocs = []
            for superviseur, ventes in groupes.items():
                blocs.append(AlerteMoteur._bloc_marge_par_agent(superviseur.full_name, ventes))
            if sans_superviseur:
                blocs.append(AlerteMoteur._bloc_marge_par_agent("Sans superviseur", sans_superviseur))

            message = (
                f"⚠️ VENTES SOUS LA MARGE MINIMALE\n{DESCRIPTIONS_ALERTES['prix']}\n\n"
                + "\n\n".join(blocs)
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="prix",
                defaults={"niveau": "critique", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("prix", [{}] if (groupes or sans_superviseur) else [])

    @staticmethod
    def _bloc_marge_par_agent(titre, ventes):
        par_agent = defaultdict(list)
        for v in ventes:
            par_agent[v["agent"]].append(v)

        sous_blocs = []
        for agent, ventes_agent in par_agent.items():
            lignes_ventes = "\n".join(
                f"• {v['produit'].nom} — vendu à {fcfa(v['prix_vente'])} FCFA\n  Marge : {fcfa(v['marge'])} FCFA"
                for v in ventes_agent
            )
            sous_blocs.append(f"{agent.full_name}\n{lignes_ventes}")

        return f"{titre}\n\n" + "\n\n".join(sous_blocs)

    # ------------------------------------------------------------------
    # Ventes à prix suspect (écart inhabituel avec le prix d'achat) — ajouté
    # 24/09/2026, complémentaire de "prix" (marge minimale) qui ne détecte que
    # les prix trop BAS. Même structure de message (un seul message, groupé
    # par superviseur puis par agent) que evaluer_variation_prix.
    # ------------------------------------------------------------------

    @staticmethod
    def evaluer_ecart_prix_achat():
        situations = PrixSurveillanceService.ventes_ecart_prix_achat_suspect()
        groupes, sans_superviseur = _grouper_par_superviseur(situations)

        if groupes or sans_superviseur:
            blocs = []
            for superviseur, ventes in groupes.items():
                blocs.append(AlerteMoteur._bloc_ecart_par_agent(superviseur.full_name, ventes))
            if sans_superviseur:
                blocs.append(AlerteMoteur._bloc_ecart_par_agent("Sans superviseur", sans_superviseur))

            message = (
                "⚠️ VENTES À PRIX SUSPECT (écart inhabituel avec le prix d'achat)\n"
                f"{DESCRIPTIONS_ALERTES['prix_ecart_achat']}\n\n" + "\n\n".join(blocs)
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="prix_ecart_achat",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue(
            "prix_ecart_achat", [{}] if (groupes or sans_superviseur) else []
        )

    @staticmethod
    def _bloc_ecart_par_agent(titre, ventes):
        par_agent = defaultdict(list)
        for v in ventes:
            par_agent[v["agent"]].append(v)

        sous_blocs = []
        for agent, ventes_agent in par_agent.items():
            lignes_ventes = "\n".join(
                f"• {v['produit'].nom} — acheté {fcfa(v['prix_achat'])} FCFA, "
                f"vendu à {fcfa(v['prix_vente'])} FCFA\n  Écart : +{fcfa(v['ecart'])} FCFA"
                for v in ventes_agent
            )
            sous_blocs.append(f"{agent.full_name}\n{lignes_ventes}")

        return f"{titre}\n\n" + "\n\n".join(sous_blocs)

    # ------------------------------------------------------------------
    # Baisse d'activité commerciale — dernière vente VALIDE de l'agent,
    # décorrélée du stock/lot (StockAgeService.agents_sans_vente_recente).
    # ------------------------------------------------------------------

    @staticmethod
    def _lignes_activite(agents):
        return "\n".join(
            f"• {a['agent'].full_name} — dernière vente : "
            f"{_fmt_date(a['derniere_vente'].date()) if a['derniere_vente'] else 'jamais'} — "
            f"{a['jours_ecoules'] if a['jours_ecoules'] is not None else '—'} jours"
            for a in agents
        )

    @staticmethod
    def evaluer_baisse_activite():
        # Un message Telegram distinct par superviseur (refonte du 24/09/2026, à la demande
        # de mdmaiga — auparavant un seul message combinant toutes les équipes), pour que
        # chaque superviseur ne reçoive que ses propres agents en baisse d'activité. Les
        # agents sans superviseur assigné restent regroupés dans un message à part (clé
        # d'identification superviseur=None, distincte des messages par superviseur).
        situations = StockAgeService.agents_sans_vente_recente()
        groupes, sans_superviseur = _grouper_par_superviseur(situations)

        for superviseur, agents in groupes.items():
            message = (
                f"⚠️ BAISSE D'ACTIVITÉ COMMERCIALE — {superviseur.full_name}\n"
                f"{DESCRIPTIONS_ALERTES['activite']}\n\n"
                f"{AlerteMoteur._lignes_activite(agents)}"
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="activite",
                defaults={"niveau": "warning", "message": message},
                superviseur=superviseur.user,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        if sans_superviseur:
            message = (
                "⚠️ BAISSE D'ACTIVITÉ COMMERCIALE — AGENTS SANS SUPERVISEUR\n"
                "Agents sans superviseur assigné, sans vente enregistrée depuis plus de 3 jours. "
                "Envoyé chaque jour tant que la situation persiste.\n\n"
                f"{AlerteMoteur._lignes_activite(sans_superviseur)}"
            )
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="activite",
                defaults={"niveau": "warning", "message": message},
                superviseur=None,
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        situations_actives = [{"superviseur": s.user} for s in groupes.keys()]
        if sans_superviseur:
            situations_actives.append({"superviseur": None})
        AlerteDeduplicationService.cloturer_si_resolue("activite", situations_actives)
