#/core/services/
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent)

from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Sum, Count, Max, F, DecimalField,Q
from django.db.models import ExpressionWrapper, DecimalField

from decimal import Decimal

from core.models import Agent, Vente



from django.core.cache import cache

class AgentAnalysisService:

    @staticmethod
    def get_agents_dashboard_snapshot():
        cache_key = "agents_dashboard:v1"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = {
            "kpis": AgentAnalysisService.get_agent_kpis(),  # counts
            "agents_stock": AgentAnalysisService.get_agents_with_stock(),
            "top_quantite": AgentAnalysisService.get_top_vendeurs_quantite(),
            "top_marge": AgentAnalysisService.get_top_vendeurs_marge(),
            "agents_actifs_72h": AgentAnalysisService.get_agents_vendu_derniere_72h(),
        }

        cache.set(cache_key, data, 60 * 10)  # 10 minutes
        return data


    @staticmethod
    def get_agent_regularity_status(jours_inactifs):
        """Détermine le statut de régularité basé sur les jours d'inactivité"""
        if jours_inactifs == "Aucune vente":
            return 'red'
        
        if jours_inactifs < 3:
            return 'green'
        elif 3 <= jours_inactifs <= 7:  
            return 'orange'
        else:
            return 'red'

    @staticmethod
    def get_agent_global_data(agent):
        """Données globales (non filtrées par période)"""
        ventes = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
        
        total_ventes = ventes.count()
        total_quantite = sum(vente.quantite for vente in ventes)
        total_ca = sum(vente.total_vente for vente in ventes)
        
        # Dernière vente
        derniere_vente = ventes.order_by('-date_vente').first()
        jours_depuis_derniere_vente = "Aucune vente"
        if derniere_vente:
            aujourd_hui = timezone.now().date()
            date_vente = derniere_vente.date_vente
            if isinstance(date_vente, datetime):
                date_vente = date_vente.date()
            jours_depuis_derniere_vente = (aujourd_hui - date_vente).days
        
        # 7 derniers jours
        date_7_jours = timezone.now() - timedelta(days=7)
        ventes_7_jours = ventes.filter(date_vente__gte=date_7_jours)
        quantite_7_jours = sum(vente.quantite for vente in ventes_7_jours)
        
        # Calcul du statut de régularité cohérent
        regularity_status = AgentAnalysisService.get_agent_regularity_status(jours_depuis_derniere_vente)
        
        return {
            'total_ventes': total_ventes,
            'total_quantite': total_quantite,
            'total_ca': total_ca,
            'jours_depuis_derniere_vente': jours_depuis_derniere_vente,
            'quantite_7_jours': quantite_7_jours,
            'regularity_status': regularity_status,
            'derniere_vente_date': derniere_vente.date_vente if derniere_vente else None,
        }

    @staticmethod
    def get_agent_current_stock(agent):
        """Récupère les produits actuellement à disposition de l'agent"""
        distributions_actives = DistributionAgent.objects.filter(
            agent_terrain=agent,
            est_supprime=False
        )
        
        stock_data = []
        total_produits = 0
        
        for distribution in distributions_actives:
            details = distribution.detaildistribution_set.filter(est_supprime=False)
            
            for detail in details:
                quantite_restante = detail.quantite_restante_calculee
                if quantite_restante > 0:
                    total_produits += 1
                    stock_data.append({
                        'distribution_date': distribution.date_distribution,
                        'produit': detail.lot.produit.nom,
                        'quantite_initiale': detail.quantite,
                        'quantite_restante': quantite_restante,
                        'prix_gros': detail.prix_gros,
                        'prix_detail': detail.prix_detail,
                        'specification': detail.specification,
                        'lot': detail.lot,
                    })
        
        return {
            'stock_details': stock_data,
            'total_produits_disponibles': total_produits,
        }

    @staticmethod
    def get_period_dates(period_type='monthly'):
        """Retourne les dates de début et fin pour une période donnée"""
        aujourd_hui = timezone.now()
        
        if period_type == 'daily':
            date_debut = aujourd_hui.replace(hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut + timedelta(days=1)
        elif period_type == 'weekly':
            date_debut = aujourd_hui - timedelta(days=aujourd_hui.weekday())
            date_debut = date_debut.replace(hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut + timedelta(days=7)
        elif period_type == 'yearly':
            date_debut = aujourd_hui.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            date_fin = date_debut.replace(year=date_debut.year + 1)
        else:  # monthly (par défaut)
            date_debut = aujourd_hui.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if aujourd_hui.month == 12:
                date_fin = date_debut.replace(year=date_debut.year + 1, month=1)
            else:
                date_fin = date_debut.replace(month=date_debut.month + 1)
        
        return date_debut, date_fin
            

    @staticmethod
    def get_agent_period_data(agent, period_type='monthly'):
        """Retourne toutes les données pour une période donnée"""
        date_debut, date_fin = AgentAnalysisService.get_period_dates(period_type)
        
        # Ventes personnelles pour la période
        ventes_periode = Vente.objects.filter(
            agent=agent,
            stagiaire__isnull=True,
            date_vente__gte=date_debut,
            date_vente__lt=date_fin
        )
        
        # Calculs de base
        nombre_ventes = ventes_periode.count()
        quantite_vendue = sum(vente.quantite for vente in ventes_periode)
        ca_total = sum(vente.total_vente for vente in ventes_periode)
        
        # Calcul de la marge
        marge_totale = Decimal('0')
        for vente in ventes_periode:
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            marge_totale += marge_vente
        
        taux_marge = (marge_totale / ca_total * 100) if ca_total > 0 else 0
        
        # Répartition par type de vente
        ventes_gros = ventes_periode.filter(type_vente='gros')
        ventes_detail = ventes_periode.filter(type_vente='detail')
        
        quantite_gros = sum(vente.quantite for vente in ventes_gros)
        quantite_detail = sum(vente.quantite for vente in ventes_detail)
        ca_gros = sum(vente.total_vente for vente in ventes_gros)
        ca_detail = sum(vente.total_vente for vente in ventes_detail)
        
        pourcentage_gros = (quantite_gros / quantite_vendue * 100) if quantite_vendue > 0 else 0
        pourcentage_detail = (quantite_detail / quantite_vendue * 100) if quantite_vendue > 0 else 0
        
        return {
            'period_type': period_type,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nombre_ventes': nombre_ventes,
            'quantite_vendue': quantite_vendue,
            'ca_total': ca_total,
            'marge_totale': marge_totale,
            'taux_marge': round(taux_marge, 1),
            'quantite_gros': quantite_gros,
            'quantite_detail': quantite_detail,
            'ca_gros': ca_gros,
            'ca_detail': ca_detail,
            'pourcentage_gros': round(pourcentage_gros, 1),
            'pourcentage_detail': round(pourcentage_detail, 1),
        }
    


    @staticmethod
    def get_agent_kpis():
        """KPI globaux agents (exclut direction)"""
        agents = Agent.objects.exclude(type_agent='direction')
        stagiaires = agents.filter(type_agent='stagiaire')
        
        return {
            'total_agents': agents.count(),
            'superviseurs': agents.filter(type_agent='entrepot').count(),
            'agents_terrain': agents.filter(type_agent='terrain').count(),
            'stagiaires_total': stagiaires.count(),
            'stagiaires_actifs': stagiaires.filter(date_expiration__gt=timezone.now()).count(),
            'stagiaires_expires': stagiaires.filter(date_expiration__lte=timezone.now()).count(),
        }


    @staticmethod
    def get_top_vendeurs_quantite(limit=5):
        """
        Top agents terrain par quantité vendue
        VERSION OPTIMISÉE – 0 N+1
        """

        ventes = (
            Vente.objects
            .filter(
                agent__type_agent='terrain',
                stagiaire__isnull=True,
                est_supprime=False
            )
            .values("agent_id")
            .annotate(
                quantite_totale=Sum("quantite"),

                quantite_gros=Sum(
                    "quantite",
                    filter=Q(type_vente='gros')
                ),

                quantite_detail=Sum(
                    "quantite",
                    filter=Q(type_vente='detail')
                ),
            )
            .order_by("-quantite_totale")[:limit]
        )

        agents = {
            a.id: a
            for a in Agent.objects.filter(
                id__in=[v["agent_id"] for v in ventes]
            )
        }

        result = []
        for v in ventes:
            agent = agents.get(v["agent_id"])
            if not agent:
                continue

            result.append({
                "agent": agent,
                "quantite_totale": v["quantite_totale"] or 0,
                "quantite_gros": v["quantite_gros"] or 0,
                "quantite_detail": v["quantite_detail"] or 0,
            })

        return result

    @staticmethod
    def get_top_vendeurs_marge(limit=5):
        """
        Top agents terrain par marge générée
        VERSION OPTIMISÉE – 0 N+1
        """

        ventes = (
            Vente.objects
            .filter(
                agent__type_agent='terrain',
                stagiaire__isnull=True,
                est_supprime=False
            )
            .annotate(
                # CA ligne
                ca_ligne=ExpressionWrapper(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                # Marge ligne = (prix vente - prix achat) * qte
                marge_ligne=ExpressionWrapper(
                    (F("prix_vente_unitaire")
                     - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
            )
            .values("agent_id")
            .annotate(
                ca_total=Sum("ca_ligne"),
                marge_totale=Sum("marge_ligne"),
                quantite_totale=Sum("quantite"),

                # Optionnel : détail gros / détail
                marge_gros=Sum(
                    "marge_ligne",
                    filter=Q(type_vente='gros')
                ),
                marge_detail=Sum(
                    "marge_ligne",
                    filter=Q(type_vente='detail')
                ),
            )
            .order_by("-marge_totale")[:limit]
        )

        agents = {
            a.id: a
            for a in Agent.objects.filter(
                id__in=[v["agent_id"] for v in ventes]
            )
        }

        result = []
        for v in ventes:
            agent = agents.get(v["agent_id"])
            if not agent:
                continue

            ca = v["ca_total"] or Decimal("0")
            marge = v["marge_totale"] or Decimal("0")
            taux_marge = (marge / ca * 100) if ca > 0 else 0

            result.append({
                "agent": agent,
                "ca_total": ca,
                "marge_totale": marge,
                "taux_marge": float(taux_marge),
                "quantite_totale": v["quantite_totale"] or 0,
                "marge_gros": v["marge_gros"] or Decimal("0"),
                "marge_detail": v["marge_detail"] or Decimal("0"),
            })

        return result


    @staticmethod
    def get_superviseurs_finance():
        """Situation financière des superviseurs"""
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        
        superviseurs_data = []
        for superviseur in superviseurs:
            # Ventes personnelles
            ventes_perso = Vente.objects.filter(agent=superviseur)
            total_ventes = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes_perso)
            
            # Recouvrements agents
            recouvrements = Recouvrement.objects.filter(superviseur=superviseur)
            total_recouvrements = sum(rec.montant_recouvre for rec in recouvrements)
            
            # Dépenses
            depenses = Depense.objects.filter(versement__superviseur=superviseur)
            total_depenses = sum(dep.montant for dep in depenses)
            
            # Versements
            versements = VersementBancaire.objects.filter(superviseur=superviseur)
            total_versements = sum(vers.montant_vente for vers in versements)
            
            # Solde
            solde = superviseur.solde_superviseur
            
            superviseurs_data.append({
                'superviseur': superviseur,
                'total_ventes': total_ventes,
                'total_recouvrements': total_recouvrements,
                'total_depenses': total_depenses,
                'total_versements': total_versements,
                'solde': solde
            })
        
        return superviseurs_data
    
    @staticmethod
    def get_competition_stagiaires():
        """Performance des stagiaires - pour ventes réalisées POUR eux"""
        stagiaires = Agent.objects.filter(type_agent='stagiaire')
        
        competition_data = []
        for stagiaire in stagiaires:
            # Ventes où le stagiaire est mentionné (réalisées par d'autres agents pour lui)
            ventes_stagiaire = Vente.objects.filter(stagiaire=stagiaire)
            total_quantite = sum(vente.quantite for vente in ventes_stagiaire)
            total_ca = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes_stagiaire)
            
            # Calcul de la MARGE pour les ventes du stagiaire
            marge_totale = Decimal('0')
            for vente in ventes_stagiaire:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_totale += marge_vente
            
            # Taux de marge
            taux_marge = (marge_totale / total_ca * 100) if total_ca > 0 else 0
            
            statut = "🟢 Actif" if stagiaire.est_expire == False else "🔴 Expiré"
            jours_restants = stagiaire.jours_restants if stagiaire.jours_restants else "Expiré"
            
            competition_data.append({
                'stagiaire': stagiaire,
                'statut': statut,
                'total_quantite': total_quantite,
                'total_ca': total_ca,
                'marge_totale': marge_totale,
                'taux_marge': round(taux_marge, 1),
                'jours_restants': jours_restants,
                'date_mise_service': stagiaire.date_mise_service,
                'nombre_ventes': ventes_stagiaire.count()
            })
        
        # Tri par MARGE (plus pertinent que CA)
        return sorted(competition_data, key=lambda x: x['total_quantite'], reverse=True)

    @staticmethod
    def get_agents_terrain_performance(mois='all'):
        """
        VERSION PRO – CONTRAT STABLE POUR LE TEMPLATE
        """

        # -------------------------
        # Filtre ventes
        # -------------------------
        ventes_filter = Q(
            agent__type_agent='terrain',
            stagiaire__isnull=True,
            est_supprime=False
        )

        if mois != 'all':
            try:
                jours = int(mois)
                ventes_filter &= Q(
                    date_vente__gte=timezone.now() - timedelta(days=jours)
                )
            except ValueError:
                pass

        # -------------------------
        # 1️⃣ AGRÉGATS SQL
        # -------------------------
        ventes = (
            Vente.objects
            .filter(ventes_filter)
            .values("agent_id")
            .annotate(
                total_quantite=Sum("quantite"),

                total_ca=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),

                marge_totale=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),

                quantite_gros=Sum(
                    "quantite",
                    filter=Q(type_vente='gros')
                ),
                quantite_detail=Sum(
                    "quantite",
                    filter=Q(type_vente='detail')
                ),

                derniere_vente=Max("date_vente"),
            )
        )

        ventes_map = {v["agent_id"]: v for v in ventes}

        # -------------------------
        # 2️⃣ AGENTS ORM
        # -------------------------
        agents = (
            Agent.objects
            .filter(type_agent='terrain')
            .select_related("user")
        )

        now = timezone.now()
        result = []

        # -------------------------
        # 3️⃣ VIEW MODEL FINAL
        # -------------------------
        for agent in agents:
            stats = ventes_map.get(agent.id)

            if not stats:
                # agent sans vente
                result.append({
                    "agent": agent,
                    "total_ca": Decimal("0"),
                    "marge_totale": Decimal("0"),
                    "total_quantite": 0,
                    "repartition": "-",
                    "derniere_vente": None,
                    "jours_depuis_derniere_vente": "Aucune vente",
                    "argent_possession": agent.argent_en_possession,
                })
                continue

            qte_total = stats["total_quantite"] or 0
            qte_gros = stats["quantite_gros"] or 0
            qte_detail = stats["quantite_detail"] or 0

            repartition = "-"
            if qte_total > 0:
                repartition = (
                    f"{round(qte_gros / qte_total * 100)}% / "
                    f"{round(qte_detail / qte_total * 100)}%"
                )

            derniere_vente = stats["derniere_vente"]
            jours_inactifs = (
                (now - derniere_vente).days
                if derniere_vente else "Aucune vente"
            )

            result.append({
                "agent": agent,
                "total_ca": stats["total_ca"] or Decimal("0"),
                "marge_totale": stats["marge_totale"] or Decimal("0"),
                "total_quantite": qte_total,
                "repartition": repartition,
                "derniere_vente": derniere_vente,
                "jours_depuis_derniere_vente": jours_inactifs,
                "argent_possession": agent.argent_en_possession,
            })

        return result

    @staticmethod
    def get_agents_terrain_performance_weekly():
        now = timezone.now()
        debut_semaine = now - timedelta(days=7)

        # -------------------------
        # FILTRES
        # -------------------------
        base_filter = Q(
            agent__type_agent='terrain',
            stagiaire__isnull=True,
            est_supprime=False
        )

        semaine_filter = base_filter & Q(date_vente__gte=debut_semaine)

        # -------------------------
        # AGRÉGATS GLOBAUX
        # -------------------------
        global_stats = (
            Vente.objects
            .filter(base_filter)
            .values("agent_id")
            .annotate(
                total_ca=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField()
                ),
                marge_totale=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField()
                ),
                total_quantite=Sum("quantite"),
                derniere_vente=Max("date_vente"),
            )
        )

        global_map = {g["agent_id"]: g for g in global_stats}

        # -------------------------
        # AGRÉGATS HEBDOMADAIRES
        # -------------------------
        weekly_stats = (
            Vente.objects
            .filter(semaine_filter)
            .values("agent_id")
            .annotate(
                ca_semaine=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField()
                ),
                marge_semaine=Sum(
                    (F("prix_vente_unitaire") - F("detail_distribution__lot__prix_achat_unitaire"))
                    * F("quantite"),
                    output_field=DecimalField()
                ),
                quantite_semaine=Sum("quantite"),
                nombre_ventes_semaine=Count("id"),
            )
        )

        weekly_map = {w["agent_id"]: w for w in weekly_stats}

        # -------------------------
        # AGENTS
        # -------------------------
        agents = (
            Agent.objects
            .filter(type_agent='terrain')
            .select_related("user")
        )

        result = []

        for agent in agents:
            g = global_map.get(agent.id, {})
            w = weekly_map.get(agent.id, {})

            derniere_vente = g.get("derniere_vente")
            jours_inactifs = (
                (now - derniere_vente).days
                if derniere_vente else "Aucune vente"
            )

            result.append({
                "agent": agent,

                # GLOBAL
                "total_ca": g.get("total_ca") or Decimal("0"),
                "marge_totale": g.get("marge_totale") or Decimal("0"),
                "total_quantite": g.get("total_quantite") or 0,
                "derniere_vente": derniere_vente,
                "jours_depuis_derniere_vente": jours_inactifs,
                "argent_possession": agent.argent_en_possession,

                # 🔥 HEBDO
                "total_ca_semaine": w.get("ca_semaine") or Decimal("0"),
                "marge_semaine": w.get("marge_semaine") or Decimal("0"),
                "total_quantite_semaine": w.get("quantite_semaine") or 0,
                "nombre_ventes_semaine": w.get("nombre_ventes_semaine") or 0,
            })

        return result

    @staticmethod
    def get_custom_period_data(agent, date_debut, date_fin):
        """Retourne les données pour une période personnalisée"""
        # Ventes personnelles pour la période personnalisée
        ventes_periode = Vente.objects.filter(
            agent=agent,
            stagiaire__isnull=True,
            date_vente__gte=date_debut,
            date_vente__lt=date_fin
        )

        # Calculs de base
        nombre_ventes = ventes_periode.count()
        quantite_vendue = sum(vente.quantite for vente in ventes_periode)
        ca_total = sum(vente.total_vente for vente in ventes_periode)

        # Calcul de la marge
        marge_totale = Decimal('0')
        for vente in ventes_periode:
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            marge_totale += marge_vente

        taux_marge = (marge_totale / ca_total * 100) if ca_total > 0 else 0

        # Répartition par type de vente
        ventes_gros = ventes_periode.filter(type_vente='gros')
        ventes_detail = ventes_periode.filter(type_vente='detail')

        quantite_gros = sum(vente.quantite for vente in ventes_gros)
        quantite_detail = sum(vente.quantite for vente in ventes_detail)
        ca_gros = sum(vente.total_vente for vente in ventes_gros)
        ca_detail = sum(vente.total_vente for vente in ventes_detail)

        pourcentage_gros = (quantite_gros / quantite_vendue * 100) if quantite_vendue > 0 else 0
        pourcentage_detail = (quantite_detail / quantite_vendue * 100) if quantite_vendue > 0 else 0

        return {
            'period_type': 'custom',
            'date_debut': date_debut,
            'date_fin': date_fin,
            'nombre_ventes': nombre_ventes,
            'quantite_vendue': quantite_vendue,
            'ca_total': ca_total,
            'marge_totale': marge_totale,
            'taux_marge': round(taux_marge, 1),
            'quantite_gros': quantite_gros,
            'quantite_detail': quantite_detail,
            'ca_gros': ca_gros,
            'ca_detail': ca_detail,
            'pourcentage_gros': round(pourcentage_gros, 1),
            'pourcentage_detail': round(pourcentage_detail, 1),
        }

    @staticmethod
    def get_agent_detailed_analysis(agent, period_filter='yearly', date_debut=None, date_fin=None):
        """Analyse détaillée complète avec support période personnalisée"""
        if period_filter == 'custom' and date_debut and date_fin:
            period_data = AgentAnalysisService.get_custom_period_data(agent, date_debut, date_fin)
        else:
            period_data = AgentAnalysisService.get_agent_period_data(agent, period_filter)

        global_data = AgentAnalysisService.get_agent_global_data(agent)
        stock_data = AgentAnalysisService.get_agent_current_stock(agent)

        return {
            'period_data': period_data,
            'global_data': global_data,
            'stock_data': stock_data,
            'argent_possession': agent.argent_en_possession,
            'total_recouvre': agent.total_recouvre,
            'nombre_ventes_stagiaires': agent.vente_set.filter(stagiaire__isnull=False).count(),
        }

    @staticmethod
    def get_agents_with_stock():
        """
        Stock actuel par agent terrain
        VERSION ORM DÉFINITIVE – SANS N+1
        """

        agents = (
            Agent.objects
            .filter(type_agent='terrain')
            .annotate(
                # Quantité distribuée à l'agent
                quantite_distribuee=Sum(
                    "distributions_recues__detaildistribution__quantite",
                    filter=Q(
                        distributions_recues__est_supprime=False,
                        distributions_recues__detaildistribution__est_supprime=False
                    )
                ),

                # Quantité vendue par l'agent
                quantite_vendue=Sum(
                    "distributions_recues__detaildistribution__vente__quantite",
                    filter=Q(
                        distributions_recues__detaildistribution__vente__est_supprime=False
                    )
                ),
            )
        )

        result = []
        for agent in agents:
            distrib = agent.quantite_distribuee or 0
            vendu = agent.quantite_vendue or 0

            result.append({
                "agent": agent,
                "quantite_distribuee": distrib,
                "quantite_vendue": vendu,
                "stock_actuel": distrib - vendu,
            })

        return result


    @staticmethod
    def get_agents_vendu_derniere_72h():
        """
        Agents terrain ayant vendu dans les dernières 72h
        VERSION ORM SAFE (Django 5.x)
        """

        limite = timezone.now() - timedelta(hours=48)

        ventes = (
            Vente.objects
            .filter(
                agent__type_agent='terrain',
                stagiaire__isnull=True,
                date_vente__gte=limite
            )
            .annotate(
                ca_ligne=ExpressionWrapper(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                )
            )
            .values("agent_id")
            .annotate(
                nombre_ventes=Count("id"),
                quantite=Sum("quantite"),
                ca=Sum("ca_ligne"),
                derniere_vente=Max("date_vente"),
            )
        )

        agents_map = {
            a.id: a
            for a in Agent.objects.filter(
                id__in=[v["agent_id"] for v in ventes]
            )
        }

        result = []
        for v in ventes:
            agent = agents_map.get(v["agent_id"])
            if not agent:
                continue

            result.append({
                "agent": agent,
                "nombre_ventes": v["nombre_ventes"] or 0,
                "quantite": v["quantite"] or 0,
                "ca": v["ca"] or Decimal("0"),
                "derniere_vente": v["derniere_vente"],
            })

        return result
