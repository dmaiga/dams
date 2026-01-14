# core/services/agent_data_service.py
from django.db.models import Sum, Count, F, DecimalField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from core.models import DistributionAgent, DetailDistribution, Vente, Recouvrement, Agent


class AgentDataService:
    
    @staticmethod
    def get_agent_stock_data(agent):
        """Récupère le stock actuel de l'agent"""
        stock_actuel = []
        valeur_stock_total = Decimal('0')
        
        if agent.est_agent_vente:  # terrain ou agent_gros
            distributions = DistributionAgent.objects.filter(
                agent_terrain=agent,
                date_distribution__lte=timezone.now()
            ).select_related('superviseur').prefetch_related(
                'detaildistribution_set__lot__produit'
            ).order_by('-date_distribution')
            
            for dist in distributions:
                details = dist.detaildistribution_set.all()
                for detail in details:
                    # Quantité vendue pour ce détail
                    ventes_detail = Vente.objects.filter(
                        detail_distribution=detail,
                        est_supprime=False
                    ).aggregate(
                        total_vendu=Coalesce(
                            Sum('quantite', output_field=DecimalField()),
                            Decimal('0')
                        )
                    )
                    
                    quantite_vendue = ventes_detail['total_vendu']
                    quantite_restante = detail.quantite - quantite_vendue
                    
                    if quantite_restante > 0:
                        # Prix selon type d'agent
                        if agent.type_agent == 'agent_gros':
                            prix_vente = detail.prix_gros or Decimal('0')
                        else:
                            prix_vente = detail.prix_detail or Decimal('0')
                        
                        valeur_restante = quantite_restante * prix_vente
                        valeur_stock_total += valeur_restante
                        
                        stock_actuel.append({
                            'distribution_date': dist.date_distribution,
                            'produit': detail.lot.produit.nom,
                            'quantite_recue': detail.quantite,
                            'quantite_vendue': quantite_vendue,
                            'quantite_restante': quantite_restante,
                            'prix_vente': prix_vente,
                            'valeur_restante': valeur_restante,
                            'specification': detail.specification,
                            'superviseur': dist.superviseur.full_name if dist.superviseur else "—",
                        })
        
        return {
            'stock_actuel': stock_actuel,
            'valeur_stock_total': valeur_stock_total
        }
    
    @staticmethod
    def get_agent_sales_stats(agent, days=30):
        """Statistiques de vente pour une période"""
        date_debut = timezone.now() - timedelta(days=days)
        
        # Base query
        ventes = Vente.objects.filter(
            agent=agent,
            date_vente__gte=date_debut,
            est_supprime=False
        )
        
        # Agréger avec output_field explicite
        stats = ventes.aggregate(
            total_ca=Coalesce(
                Sum(
                    F('quantite') * F('prix_vente_unitaire'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal('0'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            total_quantite=Coalesce(
                Sum('quantite', output_field=DecimalField()),
                Decimal('0')
            ),
            nombre_ventes=Count('id'),
            marge_totale=Coalesce(
                Sum(
                    (F('prix_vente_unitaire') - F('detail_distribution__lot__prix_achat_unitaire')) 
                    * F('quantite'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal('0'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        
        # Taux de marge
        taux_marge = Decimal('0')
        if stats['total_ca'] > 0:
            taux_marge = (stats['marge_totale'] / stats['total_ca'] * 100)
        
        # Répartition par type
        ventes_detail = ventes.filter(type_vente='detail').count()
        ventes_gros = ventes.filter(type_vente='gros').count()
        total_ventes = ventes_detail + ventes_gros
        
        repartition = {}
        if total_ventes > 0:
            repartition = {
                'detail_pourcent': (ventes_detail / total_ventes) * 100,
                'gros_pourcent': (ventes_gros / total_ventes) * 100,
                'detail_count': ventes_detail,
                'gros_count': ventes_gros,
            }
        
        return {
            'stats': stats,
            'taux_marge': taux_marge,
            'repartition': repartition,
            'periode_jours': days
        }
    
    @staticmethod
    def get_agent_recovery_data(agent):
        """Données de recouvrement"""
        if not agent.est_agent_vente:
            return {'total_recouvre': Decimal('0')}
        
        total_recouvre = Recouvrement.objects.filter(
            agent=agent
        ).aggregate(
            total=Coalesce(
                Sum('montant_recouvre', output_field=DecimalField()),
                Decimal('0')
            )
        )['total']
        
        total_ventes = AgentDataService._get_total_sales(agent)
        argent_en_possession = max(total_ventes - total_recouvre, Decimal('0'))
        
        return {
            'total_recouvre': total_recouvre,
            'total_ventes': total_ventes,
            'argent_en_possession': argent_en_possession
        }
    
    @staticmethod
    def _get_total_sales(agent):
        """Total des ventes de l'agent (historique)"""
        if not agent.est_agent_vente:
            return Decimal('0')
        
        return Vente.objects.filter(
            agent=agent,
            est_supprime=False
        ).aggregate(
            total=Coalesce(
                Sum(
                    F('quantite') * F('prix_vente_unitaire'),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
                Decimal('0')
            )
        )['total']
    
    @staticmethod
    def get_recent_sales(agent, limit=10):
        """Dernières ventes de l'agent"""
        if not agent.est_agent_vente:
            return []
        
        return Vente.objects.filter(
            agent=agent,
            est_supprime=False
        ).select_related(
            'client',
            'detail_distribution__lot__produit'
        ).order_by('-date_vente')[:limit]
    
    @staticmethod
    def get_supervised_agents(superviseur):
        """Agents supervisés par un superviseur"""
        if not superviseur.est_superviseur:
            return []
        
        return Agent.objects.filter(
            superviseur=superviseur,
            type_agent__in=['terrain', 'agent_gros'],
            est_actif=True
        ).select_related('user').order_by('type_agent', 'user__last_name')
    
    @staticmethod
    def get_agent_complete_data(agent):
        """Données complètes pour l'affichage détaillé"""
        data = {
            'agent': agent,
        }
        
        if agent.est_agent_vente:
            # Stock
            stock_data = AgentDataService.get_agent_stock_data(agent)
            data.update(stock_data)
            
            # Ventes
            sales_data = AgentDataService.get_agent_sales_stats(agent)
            data.update(sales_data)
            
            # Recouvrement
            recovery_data = AgentDataService.get_agent_recovery_data(agent)
            data.update(recovery_data)
            
            # Dernières ventes
            data['dernieres_ventes'] = AgentDataService.get_recent_sales(agent)
        
        elif agent.est_superviseur:
            # Agents supervisés
            data['agents_supervises'] = AgentDataService.get_supervised_agents(agent)
            
            # Statistiques des agents supervisés
            agents_supervises = data['agents_supervises']
            data['total_agents_supervises'] = agents_supervises.count()
            data['agents_detail_count'] = agents_supervises.filter(type_agent='terrain').count()
            data['agents_gros_count'] = agents_supervises.filter(type_agent='agent_gros').count()
        
        return data