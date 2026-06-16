from core.models import (
    Vente,
    Agent,
    Produit,
)

from django.db.models import Sum

class ListeKgVenduService:

    @staticmethod
    def get_kpis(date_debut,date_fin):
    
        ventes = Vente.objects.filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False
        )
    
        kg_total = sum(
            vente.quantite_en_kg
            for vente in ventes
        )
    
        return {
            "kg_total": kg_total,
            "nb_superviseurs":
                Agent.objects.filter(
                    type_agent="entrepot",
                    est_actif=True
                ).count(),
    
            "nb_agents":
                Agent.objects.filter(
                    type_agent__in=[
                        "terrain",
                        "agent_gros",
                        "agent_polivalent"
                    ],
                    est_actif=True
                ).count(),
    
            "nb_produits":
                Produit.objects.count(),
        }
    
    @staticmethod
    def get_superviseurs(date_debut,date_fin):
    
        resultat = []
    
        superviseurs = Agent.objects.filter(
            type_agent="entrepot",
            est_actif=True
        )
    
        for superviseur in superviseurs:
        
            ventes = Vente.objects.filter(
                agent__superviseur=superviseur,
                date_vente__date__gte=date_debut,
                date_vente__date__lte=date_fin,
                est_supprime=False
            )
    
            kg = sum(
                vente.quantite_en_kg
                for vente in ventes
            )
    
            agents_count = superviseur.agents_geres.count()
    
            resultat.append({
                "superviseur": superviseur,
                "kg": kg,
                "agents_count": agents_count,
            })
    
        resultat.sort(
            key=lambda x: x["kg"],
            reverse=True
        )
    
        return resultat
    
    @staticmethod
    def get_agents( date_debut,date_fin,superviseur=None,produit=None):
    
        ventes = Vente.objects.filter(
            date_vente__date__gte=date_debut,
            date_vente__date__lte=date_fin,
            est_supprime=False
        )
    
        if superviseur:
        
            ventes = ventes.filter(
                agent__superviseur_id=superviseur
            )
    
        if produit:
        
            ventes = ventes.filter(
                detail_distribution__lot__produit_id=produit
            )
    
        agents_data = {}
    
        for vente in ventes:
        
            agent = vente.agent
    
            if agent.id not in agents_data:
            
                agents_data[agent.id] = {
                    "agent": agent,
                    "superviseur": agent.superviseur,
                    "kg": 0,
                }
    
            agents_data[agent.id]["kg"] += (
                vente.quantite_en_kg
            )
    
        resultat = list(
            agents_data.values()
        )
    
        resultat.sort(
            key=lambda x: x["kg"],
            reverse=True
        )
    
        return resultat