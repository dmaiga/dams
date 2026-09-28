"""
Incentive reellement cedee aux agents terrain ("mamies") sur un produit vendu.

Seuls les agents terrain (type_agent='terrain') percoivent une incentive liee au produit
vendu (cf. paie/services/salaire_calculator.py::calcul_salaire_mamy) :
- si le produit porte un taux dedie (Produit.taux_incentive, FCFA/unite), l'incentive
  vaut quantite_vendue * taux_incentive ;
- sinon, repli au kilo (RegleSalaire.incentive_par_kg, taux general partage par tous les
  produits sans taux dedie) : incentive = kg_vendus * incentive_par_kg.

agent_gros a un taux fixe au carton independant du produit vendu, les superviseurs n'ont
pas d'incentive produit : ce module ne les concerne pas.

Centralise ici (au lieu d'etre recalcule independamment dans direction/services/
fournisseur_service.py et bi/views.py) pour eviter que les trois ecrans divergent sur la
formule - ce qui s'est deja produit une fois (colonne "incentive cedee" a zero pour la
plupart des produits car seul le taux dedie etait compte, pas le repli au kilo).
"""

from decimal import Decimal

from core.models import RegleSalaire

DEC_ZERO = Decimal('0.00')


def get_incentive_par_kg_terrain():
    """Taux d'incentive au kilo pour les agents terrain (repli quand un produit n'a pas de
    taux dedie). Renvoie 0 si aucune regle active n'est configuree pour ce type d'agent."""
    regle = RegleSalaire.objects.filter(type_agent='terrain', actif=True).first()
    return getattr(regle, 'incentive_par_kg', None) or DEC_ZERO


def calculer_incentive_terrain(quantite, kg, taux_incentive, incentive_par_kg):
    """
    Incentive reellement cedee pour un regroupement de ventes terrain (par lot, par produit,
    par produit x mois...) :
    - quantite : quantite vendue (unites) sur ce regroupement, deja restreinte aux ventes des
      agents terrain par l'appelant ;
    - kg : quantite vendue en kilo sur ce meme regroupement (quantite * poids_unitaire_kg,
      poids 1 par defaut pour un produit vrac) ;
    - taux_incentive : Produit.taux_incentive (FCFA/unite) ou None/0 si le produit n'a pas de
      taux dedie ;
    - incentive_par_kg : taux general de repli (get_incentive_par_kg_terrain()).
    """
    if taux_incentive:
        return quantite * taux_incentive
    return kg * incentive_par_kg


def _fmt(nombre):
    """Nombre lisible pour une formule affichee en hover : pas de zeros inutiles, separateur
    de milliers a l'espace (convention deja utilisee par direction_filters::format_number)."""
    texte = f"{nombre:,.2f}".rstrip('0').rstrip('.')
    return texte.replace(',', ' ')


def expliquer_incentive_terrain(quantite, kg, taux_incentive, incentive_par_kg):
    """
    Formule lisible (pour un `title=` de hover) expliquant le resultat de
    `calculer_incentive_terrain()` avec les memes arguments — pour que la formule affichee ne
    puisse jamais diverger du calcul reel.
    """
    if taux_incentive:
        montant = quantite * taux_incentive
        return (
            f"{_fmt(quantite)} unite(s) vendue(s) par les mamies x {_fmt(taux_incentive)} "
            f"FCFA/unite (taux dedie au produit) = {_fmt(montant)} FCFA"
        )
    montant = kg * incentive_par_kg
    return (
        f"{_fmt(kg)} kg vendus par les mamies x {_fmt(incentive_par_kg)} FCFA/kg "
        f"(repli au kilo, pas de taux dedie) = {_fmt(montant)} FCFA"
    )
