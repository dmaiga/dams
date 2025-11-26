# services.py
from core.models import Vente, LotEntrepot, Perte, Depense, Recouvrement, Dette
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta

def compute_kpis():
    # 1. Total ventes (seulement ce qui est vendu)
    ventes_total = (
        Vente.objects.aggregate(
            total=Sum(F("quantite") * F("prix_vente_unitaire"))
        )["total"] or 0
    )

    # 2. Marge brute CORRECTE (uniquement sur quantité vendue)
    marge_totale = (
        Vente.objects.aggregate(
            total=Sum(
                (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                * F("quantite")
            )
        )["total"] or 0
    )

    # 3. Stock actuel valorisé (avec sécurité anti-négatif)
    lots = LotEntrepot.objects.all()
    valeur_stock = 0
    for lot in lots:
        quantite_safe = max(0, lot.quantite_restante)
        valeur_stock += quantite_safe * lot.prix_achat_unitaire

    # 4. Valeur des pertes
    valeur_pertes = (
        Perte.objects.aggregate(
            total=Sum(F("quantite_perdue") * F("lot__prix_achat_unitaire"))
        )["total"] or 0
    )

    # 5. Dépenses totales (toutes dépenses, pas seulement mensuelles)
    depenses_total = Depense.objects.aggregate(total=Sum("montant"))["total"] or 0

    # 6. Recouvrements totaux
    recouvrements = (
        Recouvrement.objects.aggregate(
            total=Sum("montant_recouvre")
        )["total"] or 0
    )

    # 7. Chiffre d'affaires (identique aux ventes totales pour l'instant)
    chiffre_affaires = ventes_total

    return {
        "chiffre_affaires": chiffre_affaires,
        "marge_totale": marge_totale,
        "valeur_stock": valeur_stock,
        "valeur_pertes": valeur_pertes,
        "depenses_total": depenses_total,
        "recouvrements_totaux": recouvrements,
    }