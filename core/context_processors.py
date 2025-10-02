# core/context_processors.py
def agent_context(request):
    """Ajoute les données contextuelles pour les agents"""
    context = {}
    
    if hasattr(request.user, 'agent') and request.user.agent.type_agent == 'terrain':
        agent = request.user.agent
        
        # Compter les ventes de l'agent
        from core.models import Vente
        mes_ventes_count = Vente.objects.filter(agent=agent).count()
        
        # Compter les dettes en cours
        from core.models import Dette
        mes_dettes_count = Dette.objects.filter(
            vente__agent=agent,
            statut__in=['en_cours', 'partiellement_paye', 'en_retard']
        ).count()
        
        # Compter les clients de l'agent
        from core.models import Client
        mes_clients_count = Client.objects.filter(vente__agent=agent).distinct().count()
        
        # Bonus de l'agent
        mes_bonus = agent.bonus.total_bonus if hasattr(agent, 'bonus') else 0
        
        # Stock disponible pour l'agent
        from core.models import DetailDistribution
        mes_stock_disponible = DetailDistribution.objects.filter(
            distribution__agent_terrain=agent,
            quantite__gt=0
        ).count()
        
        # Montant à recouvrer
        mes_montant_recouvrer = sum(
            dette.montant_restant 
            for dette in Dette.objects.filter(
                vente__agent=agent,
                statut__in=['en_cours', 'partiellement_paye', 'en_retard']
            )
        )
        
        context.update({
            'mes_ventes_count': mes_ventes_count,
            'mes_dettes_count': mes_dettes_count,
            'mes_clients_count': mes_clients_count,
            'mes_bonus': mes_bonus,
            'mes_stock_disponible': mes_stock_disponible,
            'mes_montant_recouvrer': mes_montant_recouvrer,
        })
    
    return context