from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Produit, LotEntrepot, Vente, Fournisseur, Perte


class ProductAnalysisService:

    # ----------------------------------------------------------------------
    # 1) KPI globaux
    # ----------------------------------------------------------------------
    @staticmethod
    def get_product_kpis():
        """Calcule les KPI globaux pour tous les produits"""

        # Stock total
        total_stock = (
            LotEntrepot.objects
            .filter(quantite_restante__gt=0)
            .aggregate(total=Sum("quantite_restante"))
        )["total"] or Decimal("0")

        # Valeur du stock disponible
        lots_avec_valeur = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).annotate(
            valeur_stock=ExpressionWrapper(
                F("quantite_restante") * F("prix_achat_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        total_valeur_stock_disponible = sum(l.valeur_stock for l in lots_avec_valeur)

        # Valeur d'achat initiale
        valeur_achat_total = (
            LotEntrepot.objects
            .aggregate(total=Sum(F("quantite_initiale") * F("prix_achat_unitaire")))
        )["total"] or Decimal("0")

        # Chiffre d’affaires total
        ventes_ca = Vente.objects.annotate(
            montant=ExpressionWrapper(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        ca_total = sum(v.montant for v in ventes_ca)

        # Valeur des pertes
        pertes_valeur = Decimal("0")
        for perte in Perte.objects.select_related("lot"):
            pertes_valeur += perte.quantite_perdue * (perte.lot.prix_achat_unitaire or Decimal(0))

        # Marge totale
        marge_totale = Decimal("0")
        for vente in Vente.objects.select_related("detail_distribution__lot"):
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or 0
            marge_totale += (vente.prix_vente_unitaire - prix_achat) * vente.quantite

        return {
            "total_stock": total_stock,
            "total_valeur_stock_disponible": total_valeur_stock_disponible,
            "valeur_achat_total": valeur_achat_total,
            "ca_total": ca_total,
            "pertes_valeur": pertes_valeur,
            "marge_totale": marge_totale,
        }

    # ----------------------------------------------------------------------
    # 2) Liste des produits (optimisée ORM)
    # ----------------------------------------------------------------------
    @staticmethod
    def get_products_by_supplier(supplier_id=None):

        lots = (
            LotEntrepot.objects
            .select_related("produit", "fournisseur")
            .prefetch_related("pertes")
            .annotate(
                perte_qte=Sum("pertes__quantite_perdue", default=0),
                valeur_stock=ExpressionWrapper(
                    F("quantite_restante") * F("prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
        )

        if supplier_id:
            lots = lots.filter(fournisseur_id=supplier_id)

        produits = {}

        # On regroupe les lots par produit
        for lot in lots:
            pid = lot.produit_id

            if pid not in produits:
                produits[pid] = {
                    "product": lot.produit,
                    "lots": [],
                    "total_stock": 0,
                    "total_valeur_stock_disponible": Decimal("0"),
                    "total_initial_quantity": 0,
                    "total_losses_quantite": 0,
                    "total_losses_valeur": 0,
                    "fournisseur_specifique": lot.fournisseur if supplier_id else None,
                }

            p = produits[pid]
            p["lots"].append(lot)
            p["total_stock"] += lot.quantite_restante
            p["total_valeur_stock_disponible"] += lot.valeur_stock
            p["total_initial_quantity"] += lot.quantite_initiale

            pertes_qte = lot.perte_qte or 0
            p["total_losses_quantite"] += pertes_qte
            p["total_losses_valeur"] += pertes_qte * (lot.prix_achat_unitaire or 0)

        # ---------- Optimisation des ventes : 1 seule requête ----------
        ventes = Vente.objects.select_related("detail_distribution__lot")

        if supplier_id:
            ventes = ventes.filter(detail_distribution__lot__fournisseur_id=supplier_id)

        ventes = ventes.annotate(
            revenu=ExpressionWrapper(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            marge=ExpressionWrapper(
                (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire")) * F("quantite"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )

        ventes_par_produit = {}

        for v in ventes:
            pid = v.detail_distribution.lot.produit_id
            if pid not in ventes_par_produit:
                ventes_par_produit[pid] = {"qte": 0, "revenu": 0, "marge": 0}

            vp = ventes_par_produit[pid]
            vp["qte"] += v.quantite
            vp["revenu"] += v.revenu
            vp["marge"] += v.marge

        # ---------- Ajout des KPIs ventes ----------
        final_list = []

        for pid, data in produits.items():
            vp = ventes_par_produit.get(pid, {"qte": 0, "revenu": 0, "marge": 0})

            revenu = vp["revenu"]
            marge = vp["marge"]

            taux_marge = (marge / revenu * 100) if revenu > 0 else 0

            ts = data["total_stock"]
            if ts <= 0:
                stock_status = "RUPTURE"
            elif ts < 30:
                stock_status = "CRITIQUE"
            elif ts > 200:
                stock_status = "EXCÉDENTAIRE"
            else:
                stock_status = "NORMAL"

            data.update({
                "total_sales_quantity": vp["qte"],
                "total_sales_revenue": revenu,
                "marge_totale": marge,
                "taux_marge": float(taux_marge),
                "stock_status": stock_status,
            })

            final_list.append(data)

        return final_list

    # ----------------------------------------------------------------------
    # 3) Ventes par agent
    # ----------------------------------------------------------------------
    @staticmethod
    def get_ventes_par_agent(supplier_id=None):

        ventes = Vente.objects.select_related(
            "agent",
            "detail_distribution__lot__produit",
            "detail_distribution__lot__fournisseur"
        )

        if supplier_id:
            ventes = ventes.filter(detail_distribution__lot__fournisseur_id=supplier_id)

        ventes_par_agent = {}

        for vente in ventes:
            agent = vente.agent

            if agent.id not in ventes_par_agent:
                ventes_par_agent[agent.id] = {
                    "agent": agent,
                    "total_quantite": Decimal("0"),
                    "total_ca": Decimal("0"),
                    "total_marge": Decimal("0"),
                    "produits_vendus": set()
                }

            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal("0")
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite

            a = ventes_par_agent[agent.id]
            a["total_quantite"] += vente.quantite
            a["total_ca"] += vente.quantite * vente.prix_vente_unitaire
            a["total_marge"] += marge_vente
            a["produits_vendus"].add(vente.detail_distribution.lot.produit.nom)

        result = []

        for a in ventes_par_agent.values():
            taux = (a["total_marge"] / a["total_ca"] * 100) if a["total_ca"] > 0 else 0

            result.append({
                "agent": a["agent"],
                "total_quantite": a["total_quantite"],
                "total_ca": a["total_ca"],
                "total_marge": a["total_marge"],
                "taux_marge": float(taux),
                "nombre_produits": len(a["produits_vendus"]),
                "produits_vendus": list(a["produits_vendus"])[:3],
            })

        return sorted(result, key=lambda x: x["total_ca"], reverse=True)

    # ----------------------------------------------------------------------
    # 4) Détail produit
    # ----------------------------------------------------------------------
    
    @staticmethod
    def get_product_detail(product_id, supplier_id=None):

        try:
            product = Produit.objects.prefetch_related(
                "lots",
                "lots__fournisseur",
                "lots__pertes"
            ).get(id=product_id)

        except Produit.DoesNotExist:
            return None

        lots = product.lots.all()

        if supplier_id:
            lots = lots.filter(fournisseur_id=supplier_id)
            fournisseur_specifique = Fournisseur.objects.get(id=supplier_id)
        else:
            fournisseur_specifique = None

        # Ventes du produit
        ventes = Vente.objects.filter(detail_distribution__lot__produit=product)

        if supplier_id:
            ventes = ventes.filter(detail_distribution__lot__in=lots)

        # Calcul marge & pertes
        marge_totale = Decimal("0")
        pertes_quantite_totale = Decimal("0")
        pertes_valeur_totale = Decimal("0")

        for lot in lots:
            pertes_qte = sum(p.quantite_perdue for p in lot.pertes.all())
            pertes_quantite_totale += pertes_qte
            pertes_valeur_totale += pertes_qte * (lot.prix_achat_unitaire or 0)

        for vente in ventes:
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or 0
            marge_totale += (vente.prix_vente_unitaire - prix_achat) * vente.quantite

        sales_stats = {
            "total_quantity": sum(v.quantite for v in ventes),
            "total_revenue": sum(v.quantite * (v.prix_vente_unitaire or 0) for v in ventes),
            "total_marge": marge_totale,
            "pertes_quantite": pertes_quantite_totale,
            "pertes_valeur": pertes_valeur_totale,
            "sales_count": ventes.count()
        }

        if sales_stats["total_revenue"] > 0:
            sales_stats["taux_marge"] = float((marge_totale / sales_stats["total_revenue"]) * 100)
        else:
            sales_stats["taux_marge"] = 0.0

        # Marge par lot
        lots_avec_marge = []
        for lot in lots.order_by("-date_reception"):
            ventes_lot = ventes.filter(detail_distribution__lot=lot)
            marge_lot = sum(
                (v.prix_vente_unitaire - lot.prix_achat_unitaire) * v.quantite
                for v in ventes_lot
            )
            lots_avec_marge.append({"lot": lot, "marge": marge_lot})

        # Ventes mensuelles (12 mois)
        monthly_sales = []
        today = timezone.now()

        for i in range(12):
            month_date = today - timedelta(days=30 * i)
            debut = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin = (debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            ventes_mois = ventes.filter(date_vente__range=[debut, fin])

            marge_mois = sum(
                (v.prix_vente_unitaire - v.detail_distribution.lot.prix_achat_unitaire) * v.quantite
                for v in ventes_mois
            )

            monthly_sales.append({
                "year": debut.year,
                "month": debut.month,
                "date_debut": debut,
                "month_name": debut.strftime("%b %Y"),
                "total_quantity": sum(v.quantite for v in ventes_mois),
                "total_revenue": sum(v.quantite * (v.prix_vente_unitaire or 0) for v in ventes_mois),
                "total_marge": marge_mois,
            })

        monthly_sales.sort(key=lambda x: x["date_debut"], reverse=True)

        return {
            "product": product,
            "fournisseur_specifique": fournisseur_specifique,
            "sales_stats": sales_stats,
            "monthly_sales": monthly_sales,
            "lots_avec_marge": lots_avec_marge,
            "lots": lots.order_by("-date_reception"),
        }

    # ----------------------------------------------------------------------
    # 5) Liste des fournisseurs (non HTMX)
    # ----------------------------------------------------------------------
    @staticmethod
    def get_suppliers_with_stats():

        suppliers = Fournisseur.objects.all().order_by("nom")

        suppliers_with_stats = []

        for supplier in suppliers:
            lots = LotEntrepot.objects.filter(fournisseur=supplier)

            total_stock = sum(l.quantite_restante for l in lots)

            total_valeur_stock_disponible = sum(
                l.quantite_restante * (l.prix_achat_unitaire or 0)
                for l in lots
            )

            valeur_achat_total = sum(
                l.quantite_initiale * (l.prix_achat_unitaire or 0)
                for l in lots
            )

            ventes_fourn = Vente.objects.filter(detail_distribution__lot__fournisseur=supplier)
            marge_totale = Decimal("0")

            for vente in ventes_fourn:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or 0
                marge_totale += (vente.prix_vente_unitaire - prix_achat) * vente.quantite

            pertes_valeur = sum(
                (sum(p.quantite_perdue for p in l.pertes.all())) * (l.prix_achat_unitaire or 0)
                for l in lots
            )

            suppliers_with_stats.append({
                "id": supplier.id,
                "nom": supplier.nom,
                "product_count": Produit.objects.filter(lots__fournisseur=supplier).distinct().count(),
                "total_lots": lots.count(),
                "total_stock": total_stock,
                "total_valeur_stock_disponible": total_valeur_stock_disponible,
                "valeur_achat_total": valeur_achat_total,
                "marge_generee": marge_totale,
                "pertes_valeur": pertes_valeur,
            })

        return suppliers_with_stats
