# core/services/dashboard_service.py
from django.utils import timezone
from django.db.models import Sum, Count, Q, F, FloatField, Max, Case, When, Value, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from datetime import timedelta, datetime
from decimal import Decimal
import calendar
from django.db import models

from core.models import (
    Vente, LotEntrepot, Perte, Depense, VersementBancaire,
    Agent, Dette, Recouvrement, PaiementDette, 
    DetailDistribution, Client, Produit, RecouvrementSuperviseur
)

class DashboardService:

    @staticmethod
    def get_kpis_fournisseurs(periode_type='annee', annee=None, mois=None):
    
        from core.models import Fournisseur, Vente, PaiementFournisseur, LotEntrepot
        from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Count
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        from django.utils import timezone
    
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        now = timezone.now()
    
        fournisseurs_data = []
    
        total_dette_contractuelle = Decimal('0.00')
        total_dette_consommee = Decimal('0.00')
        total_paye_global = Decimal('0.00')
        total_reste_contractuel = Decimal('0.00')
    
        # ===============================
        # 1️⃣ AGRÉGATS LOTS (1 requête)
        # ===============================
        lots_agg = {
            x["fournisseur_id"]: x
            for x in (
                LotEntrepot.objects
                .filter(date_reception__lte=date_fin)
                .values("fournisseur_id")
                .annotate(
                    dette_contractuelle=Coalesce(
                        Sum(
                            ExpressionWrapper(
                                F("quantite_initiale") * F("prix_achat_unitaire"),
                                output_field=DecimalField()
                            )
                        ),
                        Decimal("0.00")
                    ),
                    total_lots=Count("id"),

                    lots_periode=Count(
                        "id",
                        filter=Q(date_reception__range=(date_debut, date_fin))
                    )

                )
            )
        }
    
        # ===============================
        # 2️⃣ AGRÉGATS VENTES (1 requête)
        # ===============================
        ventes_agg = {
            x["detail_distribution__lot__fournisseur_id"]: x["total"]
            for x in (
                Vente.objects
                .filter(date_vente__lte=now)
                .values("detail_distribution__lot__fournisseur_id")
                .annotate(
                    total=Coalesce(
                        Sum(
                            ExpressionWrapper(
                                F("quantite") *
                                F("detail_distribution__lot__prix_achat_unitaire"),
                                output_field=DecimalField()
                            )
                        ),
                        Decimal("0.00")
                    )
                )
            )
        }
    
        # ===============================
        # 3️⃣ AGRÉGATS PAIEMENTS (1 requête)
        # ===============================
        paiements_agg = {
            x["fournisseur_id"]: x["total"]
            for x in (
                PaiementFournisseur.objects
                .filter(est_supprime=False, date_paiement__lte=now)
                .values("fournisseur_id")
                .annotate(
                    total=Coalesce(Sum("montant"), Decimal("0.00"))
                )
            )
        }
    
        # ===============================
        # FOURNISSEURS (0 requête interne)
        # ===============================
        fournisseurs = Fournisseur.objects.order_by("nom")
    
        for fournisseur in fournisseurs:
        
            lots_data = lots_agg.get(fournisseur.id, {})
            dette_contractuelle = lots_data.get("dette_contractuelle", Decimal("0.00"))
            total_lots = lots_data.get("total_lots", 0)
            nombre_lots_periode = lots_data.get("lots_periode", 0)
    
            dette_consommee_brute = ventes_agg.get(fournisseur.id, Decimal("0.00"))
            dette_consommee = min(dette_consommee_brute, dette_contractuelle)
    
            total_paye = paiements_agg.get(fournisseur.id, Decimal("0.00"))
    
            reste_contractuel = max(
                dette_contractuelle - total_paye,
                Decimal("0.00")
            )
    
            pourcentage_paye = (
                (total_paye / dette_contractuelle) * 100
                if dette_contractuelle > 0 else 100
            )
    
            fournisseurs_data.append({
                'fournisseur': fournisseur,
                'nom': fournisseur.nom,
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
                'total_paye': total_paye,
                'reste_contractuel': reste_contractuel,
                'pourcentage_paye': round(pourcentage_paye, 2),
                'nombre_lots_periode': nombre_lots_periode,
                'total_lots': total_lots,
            })
    
            total_dette_contractuelle += dette_contractuelle
            total_dette_consommee += dette_consommee
            total_paye_global += total_paye
            total_reste_contractuel += reste_contractuel
    
        fournisseurs_data.sort(
            key=lambda x: x['reste_contractuel'],
            reverse=True
        )
    
        pourcentage_global_paye = (
            (total_paye_global / total_dette_contractuelle) * 100
            if total_dette_contractuelle > 0 else 100
        )
    
        return {
            'fournisseurs_data': fournisseurs_data,
            'dette_contractuelle': total_dette_contractuelle,
            'dette_consommee': total_dette_consommee,
            'total_paye': total_paye_global,
            'reste_contractuel': total_reste_contractuel,
            'pourcentage_global_paye': round(pourcentage_global_paye, 2),
            'nombre_fournisseurs': len(fournisseurs_data),
        }
    

    
    @staticmethod
    def get_periodes(periode_type='mois', annee=None, mois=None):
        """Retourne les dates de début et fin selon le type de période"""
        today = timezone.now()
        
        if periode_type == 'annee':
            # Période annuelle
            if annee is None:
                annee = today.year
            date_debut = datetime(annee, 1, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            date_fin = datetime(annee, 12, 31, 23, 59, 59, tzinfo=timezone.get_current_timezone())
        elif periode_type == 'mois':
            # Période mensuelle
            if annee is None:
                annee = today.year
            if mois is None:
                mois = today.month
            date_debut = datetime(annee, mois, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
            dernier_jour = calendar.monthrange(annee, mois)[1]
            date_fin = datetime(annee, mois, dernier_jour, 23, 59, 59, tzinfo=timezone.get_current_timezone())
        else:
            # Par défaut: mois en cours
            date_debut = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            dernier_jour = calendar.monthrange(today.year, today.month)[1]
            date_fin = today.replace(day=dernier_jour, hour=23, minute=59, second=59, microsecond=999999)
        
        return date_debut, date_fin
        
    @staticmethod
    def get_kpis_globaux(periode_type='mois', annee=None, mois=None):
        """🔵 Bloc 1 : KPIs globaux (argent vs volume bien séparés)"""
    
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
    
        # -------------------------
        # VENTES DE LA PÉRIODE (1 query)
        # -------------------------
        ventes_agg = Vente.objects.filter(
            date_vente__range=[date_debut, date_fin],
            est_supprime=False
        ).aggregate(
            total_ca=Coalesce(
                Sum(ExpressionWrapper(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField()
                )),
                Decimal("0.00")
            ),
            total_kg=Coalesce(
                Sum(ExpressionWrapper(
                    F("quantite") * Case(
                        When(
                            detail_distribution__lot__produit__poids_unitaire_kg__isnull=False,
                            then=F("detail_distribution__lot__produit__poids_unitaire_kg")
                        ),
                        default=Decimal("1.00"),
                        output_field=DecimalField()
                    ),
                    output_field=DecimalField()
                )),
                Decimal("0.00")
            ),
            count_ventes=Count("id")
        )
    
        total_ventes_periode = float(ventes_agg["total_ca"] or 0)
        total_quantite_vendue_kg = float(ventes_agg["total_kg"] or 0)
        nombre_ventes = ventes_agg["count_ventes"] or 0
    
        # -------------------------
        # STOCK ACTUEL (1 query)
        # -------------------------
        stock_agg = LotEntrepot.objects.aggregate(
            total_stock=Coalesce(
                Sum(ExpressionWrapper(
                    F("quantite_restante") * F("prix_achat_unitaire"),
                    output_field=DecimalField()
                )),
                Decimal("0.00")
            )
        )
        stock_total = float(stock_agg["total_stock"] or 0)
    
        # -------------------------
        # PERTES DE LA PÉRIODE (1 query)
        # -------------------------
        pertes_agg = Perte.objects.filter(
            date_perte__range=[date_debut, date_fin]
        ).aggregate(
            total_valeur=Coalesce(
                Sum(ExpressionWrapper(
                    F("quantite_perdue") * F("lot__prix_achat_unitaire"),
                    output_field=DecimalField()
                )),
                Decimal("0.00")
            )
        )
        valeur_pertes = float(pertes_agg["total_valeur"] or 0)
    
        # -------------------------
        # SOLDE SUPERVISEURS (INSTANTANÉ) (1 query)
        # -------------------------
        superviseurs = Agent.objects.filter(
            type_agent='entrepot',
            est_actif=True
        )
        solde_superviseurs = float(sum(
            float(sup.solde_reel_superviseur or 0) for sup in superviseurs
        ))
    
        # -------------------------
        # DÉPENSES DE LA PÉRIODE (1 query)
        # -------------------------
        depenses_agg = Depense.objects.filter(
            date_depense__range=[date_debut, date_fin]
        ).aggregate(
            total_depenses=Coalesce(Sum("montant"), Decimal("0.00"))
        )
        total_depenses = float(depenses_agg["total_depenses"] or 0)
    
        # -------------------------
        # MARGE BRUTE (1 query - computed in DB)
        # -------------------------
        marge_agg = Vente.objects.filter(
            date_vente__range=[date_debut, date_fin]
        ).aggregate(
            marge=Coalesce(
                Sum(ExpressionWrapper(
                    F("quantite") * (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire")),
                    output_field=DecimalField()
                )),
                Decimal("0.00")
            )
        )
        marge_brute_periode = float(marge_agg["marge"] or 0)
    
        cash_flow = total_ventes_periode - total_depenses
    
        # -------------------------
        # RETURN (7 queries total vs 825+)
        # -------------------------
        return {
            "total_ventes_periode": total_ventes_periode,
            "total_quantite_vendue_kg": total_quantite_vendue_kg,
            "stock_total": stock_total,
            "valeur_pertes": valeur_pertes,
            "solde_superviseurs": solde_superviseurs,
            "total_depenses": total_depenses,
            "marge_brute_periode": marge_brute_periode,
            "cash_flow": cash_flow,
            "nombre_ventes_periode": nombre_ventes,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "periode_type": periode_type
        }
    

    @staticmethod
    def get_stock_essentiel():
        """🟣 Bloc 2 : Stock essentiel - Données utiles (toujours actuel)"""
        from django.db.models.functions import TruncDate
        
        # 1 query: Get all lots with aggregated vente data
        lots_with_ventes = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).select_related('produit').annotate(
            valeur_stock=ExpressionWrapper(
                F("quantite_restante") * F("prix_achat_unitaire"),
                output_field=DecimalField()
            ),
            quantite_vendue_30j=Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("detail_distribution__vente__quantite") * Case(
                            When(
                                detail_distribution__vente__detail_distribution__lot__produit__poids_unitaire_kg__isnull=False,
                                then=F("detail_distribution__vente__detail_distribution__lot__produit__poids_unitaire_kg")
                            ),
                            default=Decimal("1.00"),
                            output_field=DecimalField()
                        ),
                        output_field=DecimalField()
                    ),
                    filter=Q(
                        detail_distribution__vente__date_vente__gte=timezone.now() - timedelta(days=30)
                    )
                ),
                Decimal("0.00")
            )
        ).values(
            'id', 'produit__nom', 'quantite_restante', 
            'valeur_stock', 'quantite_vendue_30j'
        ).order_by('-valeur_stock')
        
        stocks = []
        for lot in lots_with_ventes:
            quantite_restante = float(lot['quantite_restante'] or 0)
            valeur_actuelle = float(lot['valeur_stock'] or 0)
            quantite_vendue_mois = float(lot['quantite_vendue_30j'] or 0)
            
            taux_rotation = (quantite_vendue_mois / quantite_restante * 100) if quantite_restante > 0 else 0
            
            stocks.append({
                'produit': lot['produit__nom'],
                'quantite_restante': quantite_restante,
                'valeur_actuelle': valeur_actuelle,
                'taux_rotation': taux_rotation,
                'ventes_30j': quantite_vendue_mois
            })
        
        return stocks

    @staticmethod
    def get_performances_agents(periode_type='mois', annee=None, mois=None):
        """🟠 Bloc 3 : Performances des Agents avec filtre de période"""
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        
        # 1 query: Get all superviseurs with their période aggregates
        superviseurs = (
            Agent.objects
            .filter(type_agent='entrepot', est_actif=True)
            .select_related("user")
            .annotate(
                total_ventes_periode=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("vente__quantite") * F("vente__prix_vente_unitaire"),
                            output_field=DecimalField()
                        ),
                        filter=Q(vente__date_vente__range=[date_debut, date_fin])
                    ),
                    Decimal("0.00")
                ),
                total_recouvre_periode=Coalesce(
                    Sum(
                        "recouvrements__montant_recouvre",
                        filter=Q(recouvrements__date_recouvrement__range=[date_debut, date_fin])
                    ),
                    Decimal("0.00")
                ),
                count_ventes_periode=Count(
                    "vente__id",
                    filter=Q(vente__date_vente__range=[date_debut, date_fin])
                )
            )
            .order_by('-total_ventes_periode')
        )
        
        performances = []
        for sup in superviseurs:
            total_ventes = float(sup.total_ventes_periode or 0)
            count = sup.count_ventes_periode or 0
            
            performances.append({
                'superviseur': sup.user.get_full_name() if sup.user else "Unknown",
                'total_ventes': total_ventes,
                'total_recouvre': float(sup.total_recouvre_periode or 0),
                'solde_actuel': float(sup.solde_reel_superviseur or 0),
                'moyenne_vente': total_ventes / max(count, 1),
            })
        
        return performances
    
    @staticmethod
    def get_analyses_ventes_avancees(periode_type='mois', annee=None, mois=None):
        """🔴 Bloc 4 : Analyses Ventes Avancées (Direction-friendly)"""
    
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
    
        # 1 query: Aggregate ventes par produit with proper kg calculation
        ventes_par_produit = (
            Vente.objects
            .filter(date_vente__range=[date_debut, date_fin])
            .values('detail_distribution__lot__produit__nom')
            .annotate(
                quantite_total=Coalesce(Sum("quantite"), Decimal("0.00")),
                kg_total=Coalesce(
                    Sum(ExpressionWrapper(
                        F("quantite") * Case(
                            When(
                                detail_distribution__lot__produit__poids_unitaire_kg__isnull=False,
                                then=F("detail_distribution__lot__produit__poids_unitaire_kg")
                            ),
                            default=Decimal("1.00"),
                            output_field=DecimalField()
                        ),
                        output_field=DecimalField()
                    )),
                    Decimal("0.00")
                ),
                ca_total=Coalesce(
                    Sum(ExpressionWrapper(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField()
                    )),
                    Decimal("0.00")
                ),
                marge_total=Coalesce(
                    Sum(ExpressionWrapper(
                        F("quantite") * (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire")),
                        output_field=DecimalField()
                    )),
                    Decimal("0.00")
                )
            )
            .order_by('-ca_total')[:10]
        )
        
        top_produits = [
            {
                "nom": item['detail_distribution__lot__produit__nom'],
                "quantite": round(float(item['quantite_total']), 2),
                "kg_vendus": round(float(item['kg_total']), 2),
                "ca": float(item['ca_total']),
                "marge": float(item['marge_total']),
            }
            for item in ventes_par_produit
        ]
    
        # Répartition par type de vente (1 query)
        type_vente_agg = (
            Vente.objects
            .filter(date_vente__range=[date_debut, date_fin])
            .values('type_vente')
            .annotate(
                ca=Coalesce(
                    Sum(ExpressionWrapper(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField()
                    )),
                    Decimal("0.00")
                ),
                count=Count("id")
            )
        )
        
        ca_gros = 0
        ca_detail = 0
        count_gros = 0
        count_detail = 0
        
        for item in type_vente_agg:
            if item['type_vente'] == 'gros':
                ca_gros = float(item['ca'])
                count_gros = item['count']
            elif item['type_vente'] == 'detail':
                ca_detail = float(item['ca'])
                count_detail = item['count']
        
        # Répartition par mode paiement (1 query)
        mode_paiement_agg = (
            Vente.objects
            .filter(date_vente__range=[date_debut, date_fin])
            .values('mode_paiement')
            .annotate(
                ca=Coalesce(
                    Sum(ExpressionWrapper(
                        F("quantite") * F("prix_vente_unitaire"),
                        output_field=DecimalField()
                    )),
                    Decimal("0.00")
                ),
                count=Count("id")
            )
        )
        
        ca_comptant = 0
        ca_credit = 0
        count_comptant = 0
        count_credit = 0
        
        for item in mode_paiement_agg:
            if item['mode_paiement'] == 'comptant':
                ca_comptant = float(item['ca'])
                count_comptant = item['count']
            elif item['mode_paiement'] == 'credit':
                ca_credit = float(item['ca'])
                count_credit = item['count']
        
        ca_total_periode = ca_gros + ca_detail
        
        # Tendance des ventes - 1 query using aggregate
        if periode_type == 'annee':
            annee = annee or date_debut.year
            tendance_agg = (
                Vente.objects
                .filter(date_vente__year=annee)
                .extra(select={'month': 'EXTRACT(month FROM date_vente)'})
                .values('month')
                .annotate(
                    ca=Coalesce(
                        Sum(ExpressionWrapper(
                            F("quantite") * F("prix_vente_unitaire"),
                            output_field=DecimalField()
                        )),
                        Decimal("0.00")
                    ),
                    count=Count("id")
                )
                .order_by('month')
            )
            
            tendance = []
            for item in tendance_agg:
                month_num = int(item['month']) if item['month'] else 0
                tendance.append({
                    "periode": calendar.month_name[month_num] if month_num > 0 else "Unknown",
                    "ca": float(item['ca']),
                    "ventes": item['count']
                })
        else:
            # Last 30 days
            tendance_agg = (
                Vente.objects
                .filter(date_vente__range=[date_debut, date_fin])
                .extra(select={'date_only': 'DATE(date_vente)'})
                .values('date_only')
                .annotate(
                    ca=Coalesce(
                        Sum(ExpressionWrapper(
                            F("quantite") * F("prix_vente_unitaire"),
                            output_field=DecimalField()
                        )),
                        Decimal("0.00")
                    ),
                    count=Count("id")
                )
                .order_by('date_only')
            )
            
            tendance = [
                {
                    "periode": item['date_only'].strftime('%d/%m') if item['date_only'] else "Unknown",
                    "ca": float(item['ca']),
                    "ventes": item['count']
                }
                for item in tendance_agg
            ]
    
        return {
            "top_produits": top_produits,
            "repartition_type": {
                "gros": {
                    "ca": ca_gros,
                    "ventes": count_gros,
                    "pourcentage": (ca_gros / ca_total_periode * 100) if ca_total_periode > 0 else 0
                },
                "detail": {
                    "ca": ca_detail,
                    "ventes": count_detail,
                    "pourcentage": (ca_detail / ca_total_periode * 100) if ca_total_periode > 0 else 0
                }
            },
            "repartition_paiement": {
                "comptant": {
                    "ca": ca_comptant,
                    "ventes": count_comptant,
                    "pourcentage": (ca_comptant / (ca_comptant + ca_credit) * 100) if (ca_comptant + ca_credit) > 0 else 0
                },
                "credit": {
                    "ca": ca_credit,
                    "ventes": count_credit,
                    "pourcentage": (ca_credit / (ca_comptant + ca_credit) * 100) if (ca_comptant + ca_credit) > 0 else 0
                }
            },
            "tendance_ventes": tendance,
            "total_ca_periode": ca_total_periode
        }
    


    @staticmethod
    def get_annees_disponibles():
        """Retourne les années disponibles dans les données"""
        annees_ventes = Vente.objects.dates('date_vente', 'year')
        annees_depenses = Depense.objects.dates('date_depense', 'year')
        
        annees = set()
        for date in annees_ventes:
            annees.add(date.year)
        for date in annees_depenses:
            annees.add(date.year)
        
        return sorted(annees, reverse=True)
    
