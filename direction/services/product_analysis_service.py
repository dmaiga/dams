from django.db.models import (
    Sum, F, DecimalField, Q,ExpressionWrapper, Count
)

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Produit, LotEntrepot, Vente, Fournisseur, Perte
from django.core.cache import cache
from django.db.models.functions import TruncMonth

class ProductAnalysisService:

    # ----------------------------------------------------------------------
    # 1) KPI globaux
    # ----------------------------------------------------------------------
 
    @staticmethod
    def get_product_kpis():
        cache_key = "product_kpis:v2"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # =========================
        # 🔹 LOTS
        # =========================
        lots = LotEntrepot.objects.aggregate(
            total_stock=Sum("quantite_restante"),
            total_valeur_stock_disponible=Sum(
                F("quantite_restante") * F("prix_achat_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),

            # 🔥 INVESTISSEMENT GLOBAL
            valeur_investissement=Sum(
                F("quantite_initiale") * F("prix_achat_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
        )

        # =========================
        # 🔹 VENTES
        # =========================
        ventes = Vente.objects.aggregate(
            ca_total=Sum(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
            marge_totale=Sum(
                (F("prix_vente_unitaire")
                 - F("detail_distribution__lot__prix_achat_unitaire"))
                * F("quantite"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
        )

        # =========================
        # 🔹 PERTES
        # =========================
        pertes = Perte.objects.aggregate(
            pertes_valeur=Sum(
                F("quantite_perdue") * F("lot__prix_achat_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )

        data = {
            "total_stock": lots["total_stock"] or 0,
            "total_valeur_stock_disponible": lots["total_valeur_stock_disponible"] or Decimal("0"),
            "valeur_investissement": lots["valeur_investissement"] or Decimal("0"),  # ✅ CLÉ MANQUANTE
            "ca_total": ventes["ca_total"] or Decimal("0"),
            "marge_totale": ventes["marge_totale"] or Decimal("0"),
            "pertes_valeur": pertes["pertes_valeur"] or Decimal("0"),
        }

        cache.set(cache_key, data, 60 * 15)
        return data

    # ----------------------------------------------------------------------
    # 2) Liste des produits (optimisée ORM)
    # ----------------------------------------------------------------------



    @staticmethod
    def get_products_by_supplier(supplier_id=None):
        """
        LISTE PRODUITS – VERSION OPTIMISÉE & CORRIGÉE
        - plus de FieldError
        - plus de N+1
        - agrégations DB
        - cache activé
        """

        # ============================
        # 🔹 CACHE
        # ============================
        cache_key = f"products_list:{supplier_id or 'all'}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # ============================
        # 🔹 PRODUITS + AGRÉGATS LOTS
        # ============================
        produits = (
            Produit.objects
            .annotate(
                # Stock restant (> 0 uniquement)
                total_stock=Sum(
                    "lots__quantite_restante",
                    filter=Q(lots__quantite_restante__gt=0)
                ),

                # Valeur du stock restant
                total_valeur_stock=Sum(
                    F("lots__quantite_restante") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                    filter=Q(lots__quantite_restante__gt=0)
                ),

                # Quantité initiale totale
                total_initial_quantity=Sum("lots__quantite_initiale"),

                # Pertes
                total_losses_quantite=Sum("lots__pertes__quantite_perdue"),
                total_losses_valeur=Sum(
                    F("lots__pertes__quantite_perdue") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            )
        )

        if supplier_id:
            produits = produits.filter(lots__fournisseur_id=supplier_id)

        # ============================
        # 🔹 VENTES AGRÉGÉES PAR PRODUIT
        # ============================
        ventes = (
            Vente.objects
            .values("detail_distribution__lot__produit_id")
            .annotate(
                total_sales_quantity=Sum("quantite"),
                total_sales_revenue=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                marge_totale=Sum(
                    (F("prix_vente_unitaire")
                     - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            )
        )

        if supplier_id:
            ventes = ventes.filter(
                detail_distribution__lot__fournisseur_id=supplier_id
            )

        ventes_map = {
            row["detail_distribution__lot__produit_id"]: row
            for row in ventes
        }

        # ============================
        # 🔹 FORMATAGE FINAL (PYTHON LÉGER)
        # ============================
        final_list = []

        for p in produits:
            vente = ventes_map.get(p.id, {})

            revenu = vente.get("total_sales_revenue") or Decimal("0")
            marge = vente.get("marge_totale") or Decimal("0")

            taux_marge = float((marge / revenu) * 100) if revenu > 0 else 0.0

            stock = p.total_stock or 0
            if stock <= 0:
                stock_status = "RUPTURE"
            elif stock < 30:
                stock_status = "CRITIQUE"
            elif stock > 200:
                stock_status = "EXCÉDENTAIRE"
            else:
                stock_status = "NORMAL"

            final_list.append({
                "product": p,
                # conservé pour compatibilité template
                "lots": [],

                # Stocks
                "total_stock": stock,
                "total_valeur_stock_disponible": p.total_valeur_stock or Decimal("0"),
                "total_initial_quantity": p.total_initial_quantity or 0,

                # Pertes
                "total_losses_quantite": p.total_losses_quantite or 0,
                "total_losses_valeur": p.total_losses_valeur or Decimal("0"),

                # Ventes
                "total_sales_quantity": vente.get("total_sales_quantity", 0),
                "total_sales_revenue": revenu,
                "marge_totale": marge,
                "taux_marge": taux_marge,

                # UI
                "stock_status": stock_status,
                "fournisseur_specifique": None,
            })

        # ============================
        # 🔹 CACHE
        # ============================
        cache.set(cache_key, final_list, 60 * 10)

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
        """
        Détail produit – VERSION OPTIMISÉE
        - 0 N+1
        - calculs DB
        - prêt pour cache
        """

        # ============================
        # 🔹 CACHE (par produit + fournisseur)
        # ============================
        cache_key = f"product_detail:{product_id}:{supplier_id or 'all'}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        # ============================
        # 🔹 PRODUIT + LOTS
        # ============================
        try:
            product = Produit.objects.get(id=product_id)
        except Produit.DoesNotExist:
            return None

        lots = (
            LotEntrepot.objects
            .filter(produit_id=product_id)
            .select_related("fournisseur")
            .annotate(
                pertes_quantite=Sum("pertes__quantite_perdue", default=0),
                pertes_valeur=Sum(
                    F("pertes__quantite_perdue") * F("prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                    default=0
                )
            )
        )

        fournisseur_specifique = None
        if supplier_id:
            lots = lots.filter(fournisseur_id=supplier_id)
            fournisseur_specifique = Fournisseur.objects.filter(id=supplier_id).first()

        # ============================
        # 🔹 VENTES DU PRODUIT (1 QUERY)
        # ============================
        ventes = (
            Vente.objects
            .filter(detail_distribution__lot__produit_id=product_id)
            .select_related("detail_distribution__lot")
        )

        if supplier_id:
            ventes = ventes.filter(detail_distribution__lot__fournisseur_id=supplier_id)

        ventes = ventes.annotate(
            revenu=ExpressionWrapper(
                F("quantite") * F("prix_vente_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            marge=ExpressionWrapper(
                (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                * F("quantite"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )

        # ============================
        # 🔹 STATS GLOBALES (1 QUERY)
        # ============================
        stats = ventes.aggregate(
            total_quantity=Sum("quantite"),
            total_revenue=Sum("revenu"),
            total_marge=Sum("marge"),
            sales_count=Count("id")
        )

        total_revenue = stats["total_revenue"] or Decimal("0")
        total_marge = stats["total_marge"] or Decimal("0")

        # ============================
        # 🔹 PERTES TOTALES (1 QUERY)
        # ============================
        pertes = Perte.objects.filter(lot__in=lots).aggregate(
            pertes_quantite=Sum("quantite_perdue"),
            pertes_valeur=Sum(
                F("quantite_perdue") * F("lot__prix_achat_unitaire"),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )

        # ============================
        # 🔹 STATS FINALES
        # ============================
        sales_stats = {
            "total_quantity": stats["total_quantity"] or 0,
            "total_revenue": total_revenue,
            "total_marge": total_marge,
            "pertes_quantite": pertes["pertes_quantite"] or 0,
            "pertes_valeur": pertes["pertes_valeur"] or Decimal("0"),
            "sales_count": stats["sales_count"] or 0,
            "taux_marge": float((total_marge / total_revenue) * 100) if total_revenue > 0 else 0.0,
        }

        # ============================
        # 🔹 MARGE PAR LOT (1 QUERY)
        # ============================
        marge_par_lot = (
            ventes.values("detail_distribution__lot_id")
            .annotate(
                marge=Sum("marge")
            )
        )

        marge_map = {
            row["detail_distribution__lot_id"]: row["marge"]
            for row in marge_par_lot
        }

        lots_avec_marge = [
            {
                "lot": lot,
                "marge": marge_map.get(lot.id, Decimal("0"))
            }
            for lot in lots.order_by("-date_reception")
        ]

        # ============================
        # 🔹 VENTES MENSUELLES (12 MOIS – 1 QUERY)
        # ============================
        today = timezone.now()

        monthly_sales_qs = (
            ventes
            .annotate(month=TruncMonth("date_vente"))
            .values("month")
            .annotate(
                total_quantity=Sum("quantite"),
                total_revenue=Sum("revenu"),
                total_marge=Sum("marge")
            )
            .order_by("-month")[:12]
        )

        monthly_sales = [
            {
                "year": row["month"].year,
                "month": row["month"].month,
                "date_debut": row["month"],
                "month_name": row["month"].strftime("%b %Y"),
                "total_quantity": row["total_quantity"] or 0,
                "total_revenue": row["total_revenue"] or Decimal("0"),
                "total_marge": row["total_marge"] or Decimal("0"),
            }
            for row in monthly_sales_qs
        ]

        # ============================
        # 🔹 RÉSULTAT FINAL
        # ============================
        result = {
            "product": product,
            "fournisseur_specifique": fournisseur_specifique,
            "sales_stats": sales_stats,
            "monthly_sales": monthly_sales,
            "lots_avec_marge": lots_avec_marge,
            "lots": lots.order_by("-date_reception"),
        }

        # ============================
        # 🔹 CACHE
        # ============================
        cache.set(cache_key, result, 60 * 10)

        return result


    # ----------------------------------------------------------------------
    # 5) Liste des fournisseurs 
    # ----------------------------------------------------------------------

    @staticmethod
    def get_suppliers_with_stats():
        """
        FOURNISSEURS – VERSION OPTIMISÉE
        - 0 N+1
        - agrégations DB
        - cache activé
        """

        cache_key = "suppliers_stats:v1"
        cached = cache.get(cache_key)
        if cached:
            return cached

        suppliers = (
            Fournisseur.objects
            .annotate(
                # Lots
                total_lots=Count("lots", distinct=True),
                total_stock=Sum("lots__quantite_restante"),
                total_valeur_stock_disponible=Sum(
                    F("lots__quantite_restante") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                valeur_investissement=Sum(
                    F("lots__quantite_initiale") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                valeur_achat_total=Sum(
                    F("lots__quantite_initiale") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),

                # Pertes
                pertes_valeur=Sum(
                    F("lots__pertes__quantite_perdue") * F("lots__prix_achat_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),

                # Produits distincts
                product_count=Count("lots__produit", distinct=True),

                # Ventes
                total_quantite_vendue=Sum("lots__detaildistribution__vente__quantite"),
                total_ca=Sum(
                    F("lots__detaildistribution__vente__quantite")
                    * F("lots__detaildistribution__vente__prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                marge_generee=Sum(
                    (
                        F("lots__detaildistribution__vente__prix_vente_unitaire")
                        - F("lots__prix_achat_unitaire")
                    )
                    * F("lots__detaildistribution__vente__quantite"),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            )
            .order_by("nom")
        )

        result = []

        for s in suppliers:
            result.append({
                "id": s.id,
                "nom": s.nom,
                "product_count": s.product_count or 0,
                "total_lots": s.total_lots or 0,
                "total_stock": s.total_stock or 0,
                "total_valeur_stock_disponible": s.total_valeur_stock_disponible or Decimal("0"),
                "valeur_achat_total": s.valeur_achat_total or Decimal("0"),
                "marge_generee": s.marge_generee or Decimal("0"),
                "pertes_valeur": s.pertes_valeur or Decimal("0"),
                "total_ca": s.total_ca or Decimal("0"),
                "total_quantite_vendue": s.total_quantite_vendue or 0,
                "valeur_investissement": s.valeur_investissement or Decimal("0"),

            })

        cache.set(cache_key, result, 60 * 15)
        return result
