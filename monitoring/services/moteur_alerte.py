from collections import defaultdict

from core.models import RecouvrementSuperviseur
from core.templatetags.format_fcfa import fcfa
from finance.services import lister_soldes_superviseurs, solde_superviseur
from monitoring.providers.telegram import TelegramProvider
from monitoring.services.deduplication_service import AlerteDeduplicationService
from surveillance.services.prix_service import PrixSurveillanceService
from surveillance.services.stock_age_service import StockAgeService


def _fmt_date(valeur):
    return valeur.strftime('%d/%m/%Y') if valeur else '—'


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
                            f"Solde persistant chez {superviseur} : encore débiteur après "
                            "3 cycles de remise consécutifs."
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
            message = f"⚠️ SOLDES SUPERVISEURS\n\n{lignes}"
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
            message = f"⚠️ STOCK DORMANT — ENTREPÔT\n\n{corps}"
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_entrepot",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("stock_entrepot", [{}] if lignes else [])

    @staticmethod
    def _envoyer_stock_superviseurs(lignes):
        groupes, _sans_superviseur = _grouper_par_superviseur(lignes)
        # Une AffectationLotSuperviseur porte toujours un superviseur (FK non
        # nullable) : _sans_superviseur est ici toujours vide, ignoré.

        if groupes:
            blocs = []
            for superviseur, produits in groupes.items():
                lignes_produits = "\n".join(
                    f"• {p['produit'].nom} — reçu le {_fmt_date(p['date_reference'])} — {p['jours_ecoules']} jours"
                    for p in produits
                )
                blocs.append(f"{superviseur.full_name}\n{lignes_produits}")
            message = "⚠️ STOCK EN RÉTENTION — SUPERVISEURS\n\n" + "\n\n".join(blocs)
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_superviseur",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("stock_superviseur", [{}] if groupes else [])

    @staticmethod
    def _envoyer_stock_agents(lignes):
        groupes, _sans_superviseur = _grouper_par_superviseur(lignes)
        # Un agent de vente sans superviseur assigné ne devrait pas exister en
        # pratique (Constat 9) ; s'il se présente, ses lignes de stock sont
        # simplement ignorées ici plutôt que rattachées à un superviseur
        # inventé — elles restent visibles depuis le dashboard surveillance.

        if groupes:
            blocs = []
            for superviseur, produits_agents in groupes.items():
                par_agent = defaultdict(list)
                for p in produits_agents:
                    par_agent[p["agent"]].append(p)
                sous_blocs = []
                for agent, produits in par_agent.items():
                    lignes_produits = "\n".join(
                        f"• {p['produit'].nom} — {p['jours_ecoules']} jours" for p in produits
                    )
                    sous_blocs.append(f"{agent.full_name}\n{lignes_produits}")
                blocs.append(f"{superviseur.full_name}\n\n" + "\n\n".join(sous_blocs))
            message = "⚠️ STOCK CHEZ LES AGENTS\n\n" + "\n\n".join(blocs)
            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="stock_agent",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue("stock_agent", [{}] if groupes else [])

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

            message = "⚠️ VENTES SOUS LA MARGE MINIMALE\n\n" + "\n\n".join(blocs)
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
    # Baisse d'activité commerciale — dernière vente VALIDE de l'agent,
    # décorrélée du stock/lot (StockAgeService.agents_sans_vente_recente).
    # ------------------------------------------------------------------

    @staticmethod
    def evaluer_baisse_activite():
        situations = StockAgeService.agents_sans_vente_recente()
        groupes, sans_superviseur = _grouper_par_superviseur(situations)

        if groupes or sans_superviseur:
            blocs = []
            for superviseur, agents in groupes.items():
                lignes_agents = "\n".join(
                    f"• {a['agent'].full_name} — dernière vente : "
                    f"{_fmt_date(a['derniere_vente'].date()) if a['derniere_vente'] else 'jamais'} — "
                    f"{a['jours_ecoules'] if a['jours_ecoules'] is not None else '—'} jours"
                    for a in agents
                )
                blocs.append(f"{superviseur.full_name}\n\n{lignes_agents}")
            message = "⚠️ BAISSE D'ACTIVITÉ COMMERCIALE\n\n" + "\n\n".join(blocs)

            if sans_superviseur:
                lignes_orphelins = "\n".join(
                    f"• {a['agent'].full_name} — dernière vente : "
                    f"{_fmt_date(a['derniere_vente'].date()) if a['derniere_vente'] else 'jamais'} — "
                    f"{a['jours_ecoules'] if a['jours_ecoules'] is not None else '—'} jours"
                    for a in sans_superviseur
                )
                message += f"\n\n⚠️ AGENTS SANS SUPERVISEUR\n\n{lignes_orphelins}"

            alerte, _cree, doit_envoyer = AlerteDeduplicationService.get_ou_creer(
                type_alerte="activite",
                defaults={"niveau": "warning", "message": message},
            )
            if doit_envoyer:
                TelegramProvider.send(alerte)

        AlerteDeduplicationService.cloturer_si_resolue(
            "activite", [{}] if (groupes or sans_superviseur) else []
        )
