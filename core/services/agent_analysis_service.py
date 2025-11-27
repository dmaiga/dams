from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import (Agent, Vente, Recouvrement, 
                         VersementBancaire, Depense,DetailDistribution,
                         DistributionAgent)


class AgentAnalysisService:
    
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
            
            # CALCUL CORRECT DU BONUS 48H
            maintenant = timezone.now()
            
            # Pour chaque vente, vérifier s'il y a eu recouvrement dans les 48h
            ventes_avec_bonus = 0
            montant_bonus_total = Decimal('0')
            montant_recouvre_48h = Decimal('0')
            
            for vente in ventes:
                # Chercher les recouvrements pour cette vente (ou période correspondante)
                recouvrements_vente = Recouvrement.objects.filter(
                    agent=agent,
                    date_recouvrement__gte=vente.date_vente,
                    date_recouvrement__lte=vente.date_vente + timedelta(hours=48)
                )
                
                if recouvrements_vente.exists():
                    # Cette vente a été recouvrée dans les 48h → Éligible au bonus
                    ventes_avec_bonus += 1
                    
                    # Calculer le bonus (exemple: 100 FCFA par produit)
                    bonus_vente = vente.quantite * Decimal('100')
                    montant_bonus_total += bonus_vente
                    
                    # Montant recouvré pour cette vente
                    montant_recouvre_48h += sum(rec.montant_recouvre for rec in recouvrements_vente)
            
            # Statut produits à disposition
            a_produits_disponibles = produits_restants_total > 0
            
            agents_data.append({
                'agent': agent,
                'total_ca': total_ca,
                'marge_totale': marge_totale,
                'total_quantite': total_quantite,
                'repartition': f"{round(pourcentage_gros)}%/{round(pourcentage_detail)}%",
                'produits_distincts': produits_distincts,
                'ventes_avec_bonus': ventes_avec_bonus,
                'montant_bonus_total': montant_bonus_total,
                'montant_recouvre_48h': montant_recouvre_48h,
                'produits_restants': produits_restants_total,
                'a_produits_disponibles': a_produits_disponibles,
                'argent_possession': agent.argent_en_possession,
            })
        
        return sorted(agents_data, key=lambda x: x['total_ca'], reverse=True)

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
    