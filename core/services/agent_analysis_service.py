from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense, DetailDistribution,
                         DistributionAgent)

from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, datetime


class AgentAnalysisService:
    


    @staticmethod
    def get_agent_regularity_status(jours_inactifs):
        """Détermine le statut de régularité basé sur les jours d'inactivité"""
        if jours_inactifs == "Aucune vente":
            return 'red'
        
        if jours_inactifs < 2:
            return 'green'
        elif 2 <= jours_inactifs <= 7:  
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
    def get_agent_detailed_analysis(agent, period_filter='monthly'):
        """Analyse détaillée complète"""
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
        """Top vendeurs par quantité vendue (VENTES PERSONNELLES uniquement)"""
        agents = Agent.objects.exclude(type_agent='direction')
        
        vendeurs_data = []
        for agent in agents:
            # VENTES PERSONNELLES uniquement (sans stagiaire)
            ventes = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
            total_quantite = sum(vente.quantite for vente in ventes)
            
            if total_quantite > 0:
                ventes_gros = ventes.filter(type_vente='gros')
                ventes_detail = ventes.filter(type_vente='detail')
                
                quantite_gros = sum(vente.quantite for vente in ventes_gros)
                quantite_detail = sum(vente.quantite for vente in ventes_detail)
                pourcentage_gros = (quantite_gros / total_quantite * 100) if total_quantite > 0 else 0
                
                vendeurs_data.append({
                    'agent': agent,
                    'total_quantite': total_quantite,
                    'quantite_gros': quantite_gros,
                    'quantite_detail': quantite_detail,
                    'pourcentage_gros': round(pourcentage_gros, 1)
                })
        
        return sorted(vendeurs_data, key=lambda x: x['total_quantite'], reverse=True)[:limit]
    
    @staticmethod
    def get_top_vendeurs_marge(limit=5):
        """Top vendeurs par MARGE (VENTES PERSONNELLES uniquement)"""
        agents = Agent.objects.exclude(type_agent='direction')
        
        vendeurs_data = []
        for agent in agents:
            # VENTES PERSONNELLES uniquement (sans stagiaire)
            ventes = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
            total_ca = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes)
            
            if total_ca > 0:
                # Calcul de la marge pour VENTES PERSONNELLES uniquement
                marge_totale = Decimal('0')
                for vente in ventes:
                    prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                    marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                    marge_totale += marge_vente
                
                taux_marge = (marge_totale / total_ca * 100) if total_ca > 0 else 0
                
                vendeurs_data.append({
                    'agent': agent,
                    'total_ca': total_ca,
                    'marge_totale': marge_totale,
                    'taux_marge': round(taux_marge, 1)
                })
        
        # Tri par MARGE (pas par CA)
        return sorted(vendeurs_data, key=lambda x: x['marge_totale'], reverse=True)[:limit]


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
    def get_agents_terrain_performance(mois=None):
        """Performance des agents terrain avec filtre mensuel"""
        agents = Agent.objects.filter(type_agent='terrain')
        
        # Calcul de la période si filtre mensuel
        date_debut = None
        if mois:
            today = timezone.now()
            if mois == '30':
                date_debut = today - timedelta(days=30)
            elif mois == '60':
                date_debut = today - timedelta(days=60)
            elif mois == '90':
                date_debut = today - timedelta(days=90)
        
        agents_data = []
        for agent in agents:
            # VENTES PERSONNELLES uniquement avec filtre temporel
            ventes = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
            
            if date_debut:
                ventes = ventes.filter(date_vente__gte=date_debut)
            
            total_quantite = sum(vente.quantite for vente in ventes)
            total_ca = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes)
            
            # Calcul de la MARGE
            marge_totale = Decimal('0')
            for vente in ventes:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_totale += marge_vente
            
            # Répartition gros/détail
            ventes_gros = ventes.filter(type_vente='gros')
            ventes_detail = ventes.filter(type_vente='detail')
            
            quantite_gros = sum(vente.quantite for vente in ventes_gros)
            quantite_detail = sum(vente.quantite for vente in ventes_detail)
            
            pourcentage_gros = (quantite_gros / total_quantite * 100) if total_quantite > 0 else 0
            pourcentage_detail = (quantite_detail / total_quantite * 100) if total_quantite > 0 else 0
            
            # Nombre de produits DISTINCTS vendus
            produits_distincts = ventes.values('detail_distribution__lot__produit').distinct().count()
            
            # CALCUL DES PRODUITS RESTANTS
            produits_restants_total = 0
            distributions = DistributionAgent.objects.filter(
                agent_terrain=agent,
                est_supprime=False
            )
            
            for distribution in distributions:
                details_distribution = distribution.detaildistribution_set.filter(est_supprime=False)
                for detail in details_distribution:
                    quantite_vendue = Vente.objects.filter(
                        detail_distribution=detail
                    ).aggregate(total=Sum('quantite'))['total'] or 0
                    
                    quantite_restante = detail.quantite - quantite_vendue
                    if quantite_restante > 0:
                        produits_restants_total += 1
            
            # Dernière vente et jours depuis dernière vente
            derniere_vente = ventes.aggregate(derniere_date=Max('date_vente'))['derniere_date']
            jours_depuis_derniere_vente = "Aucune vente"
            if derniere_vente:
                aujourd_hui = timezone.now().date()
                if isinstance(derniere_vente, datetime):
                    derniere_vente = derniere_vente.date()
                jours_depuis_derniere_vente = (aujourd_hui - derniere_vente).days
            
            # Statut produits à disposition
            a_produits_disponibles = produits_restants_total > 0
            
            agents_data.append({
                'agent': agent,
                'total_ca': total_ca,
                'marge_totale': marge_totale,
                'total_quantite': total_quantite,
                'repartition': f"{round(pourcentage_gros)}%/{round(pourcentage_detail)}%",
                'produits_distincts': produits_distincts,
                'produits_restants': produits_restants_total,
                'a_produits_disponibles': a_produits_disponibles,
                'argent_possession': agent.argent_en_possession,
                'derniere_vente': derniere_vente,
                'jours_depuis_derniere_vente': jours_depuis_derniere_vente,
            })
        
        return sorted(agents_data, key=lambda x: x['total_ca'], reverse=True)

    @staticmethod
    def get_agents_terrain_performance_weekly():
        """Performance des agents terrain pour la semaine en cours"""
        agents = Agent.objects.filter(type_agent='terrain')
        
        # Dates pour la semaine en cours
        aujourd_hui = timezone.now()
        debut_semaine = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        debut_semaine = debut_semaine.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_semaine = debut_semaine + timedelta(days=7)
        
        agents_data = []
        for agent in agents:
            # VENTES PERSONNELLES pour la semaine en cours
            ventes_semaine = Vente.objects.filter(
                agent=agent, 
                stagiaire__isnull=True,
                date_vente__gte=debut_semaine,
                date_vente__lt=fin_semaine
            )
            
            total_quantite_semaine = sum(vente.quantite for vente in ventes_semaine)
            total_ca_semaine = sum(vente.quantite * vente.prix_vente_unitaire for vente in ventes_semaine)
            
            # Calcul de la MARGE pour la semaine
            marge_semaine = Decimal('0')
            for vente in ventes_semaine:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_semaine += marge_vente
            
            # Dernière vente (toutes périodes)
            ventes_totales = Vente.objects.filter(agent=agent, stagiaire__isnull=True)
            derniere_vente = ventes_totales.aggregate(derniere_date=Max('date_vente'))['derniere_date']
            jours_depuis_derniere_vente = "Aucune vente"
            if derniere_vente:
                aujourd_hui_date = timezone.now().date()
                if isinstance(derniere_vente, datetime):
                    derniere_vente = derniere_vente.date()
                jours_depuis_derniere_vente = (aujourd_hui_date - derniere_vente).days
            
            agents_data.append({
                'agent': agent,
                'total_ca_semaine': total_ca_semaine,
                'marge_semaine': marge_semaine,
                'total_quantite_semaine': total_quantite_semaine,
                'jours_depuis_derniere_vente': jours_depuis_derniere_vente,
                'derniere_vente': derniere_vente,
                'nombre_ventes_semaine': ventes_semaine.count(),
            })
        
        return sorted(agents_data, key=lambda x: x['total_ca_semaine'], reverse=True)