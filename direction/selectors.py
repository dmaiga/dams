from core.models import (
    LotEntrepot,
    Perte,
    Vente,
    Agent,
    Dette,
    Depense,
    Recouvrement,
)
from django.db.models import Sum, F


# =======================
#  STOCK
# =======================
def get_stock_global():
    lots = LotEntrepot.objects.all()

    total_initial = lots.aggregate(
        total=Sum(F("quantite_initiale") * F("prix_achat_unitaire"))
    )["total"] or 0

    total_actuel = lots.aggregate(
        total=Sum(F("quantite_restante") * F("prix_achat_unitaire"))
    )["total"] or 0

    pertes_total = (
        Perte.objects.aggregate(
            total=Sum("quantite_perdue")
        )["total"] or 0
    )

    return {
        "valeur_totale_initiale": total_initial,
        "valeur_totale_actuelle": total_actuel,
        "quantite_perdue_totale": pertes_total,
    }


def get_lots_details():
    lots = (
        LotEntrepot.objects.select_related("produit")
        .annotate(
            # sécurité : jamais de négatif
            quantite_restante_safe=F("quantite_restante"),
            valeur_initiale=F("quantite_initiale") * F("prix_achat_unitaire"),
            valeur_actuelle=F("quantite_restante") * F("prix_achat_unitaire"),
            pertes=Sum("perte__quantite_perdue"),
        )
        .order_by("-date_reception")
    )

    # Post-traitement Python pour garantir quantités >= 0
    for lot in lots:
        if lot.quantite_restante_safe < 0:
            lot.quantite_restante_safe = 0

    return lots


# =======================
#  VENTES
# =======================
def get_ventes_direction():
    return (
        Vente.objects
        .select_related("agent", "client", "detail_distribution__lot__produit")
        .order_by("-date_vente")
        [:200]  # limiter pour performance
    )


# =======================
#  AGENTS
# =======================
def get_agents_performance():
    return (
        Agent.objects.select_related("user")
        .all()
        .order_by("type_agent", "user__username")
    )


# =======================
#  DETTES
# =======================
def get_dettes_direction():
    return (
        Dette.objects.select_related("vente", "vente__client", "vente__agent")
        .order_by("-date_creation")
    )


# =======================
#  DEPENSES
# =======================
def get_depenses_direction():
    return (
        Depense.objects
        .select_related("versement__superviseur")
        .order_by("-date_depense")
    )



# selectors.py - Ajouts nécessaires
def get_depenses_direction():
    depenses = Depense.objects.select_related("versement__superviseur__user").order_by("-date_depense")
    
    total_depenses = depenses.aggregate(total=Sum("montant"))["total"] or 0
    
    return {
        "depenses": depenses,
        "total_depenses": total_depenses
    }