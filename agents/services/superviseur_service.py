from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, F, Q, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal

from core.models import (
    Agent, Vente, DistributionAgent,
    LotEntrepot, Dette, Recouvrement,
    VersementBancaire, Depense
)


class SuperviseurDashboardService:
    """
    Service pour le dashboard SUPERVISEUR - PÉRIMÈTRE RESTREINT
    Ne montre que le stock attribué et les agents sous sa responsabilité
    """

    @staticmethod
    def get_superviseur(user):
        try:
            return Agent.objects.get(
                user=user,
                type_agent__in=['entrepot', 'rot']
            )
        except Agent.DoesNotExist:
            return None

    # =========================
    # STOCK ATTRIBUÉ AU SUPERVISEUR
    # =========================
    @staticmethod
    def get_stock_superviseur(superviseur):
        """
        Retourne uniquement le stock attribué à ce superviseur
        À adapter selon votre logique d'attribution de stock
        """
        # OPTION 1: Via les distributions faites par le superviseur
        distributions_ids = DistributionAgent.objects.filter(
            superviseur=superviseur
        ).values_list('id', flat=True)
        
        # Récupérer les lots distribués par ce superviseur
        lots_distribues = LotEntrepot.objects.filter(
            detaildistribution__distribution_id__in=distributions_ids
        ).distinct()
        
        # OPTION 2: Si vous avez un modèle d'attribution directe
        # lots_distribues = superviseur.lots_affectes.all()
        
        # Calcul du stock restant attribué
        stock_total = lots_distribues.aggregate(
            total_quantite=Coalesce(Sum('quantite_restante'), Decimal('0')),
            total_valeur=Coalesce(
                Sum(F('quantite_restante') * F('prix_achat_unitaire')), 
                Decimal('0')
            )
        )
        
        # Produits en stock par produit
        produits_stock = lots_distribues.filter(
            quantite_restante__gt=0
        ).values(
            'produit__nom'
        ).annotate(
            quantite_totale=Coalesce(Sum('quantite_restante'), Decimal('0')),
            valeur_totale=Coalesce(
                Sum(F('quantite_restante') * F('prix_achat_unitaire')), 
                Decimal('0')
            )
        ).order_by('-quantite_totale')
        
        # Alertes stock faible (seuil de 10)
        seuil_stock_faible = 10
        stocks_faibles = lots_distribues.filter(
            quantite_restante__lte=seuil_stock_faible,
            quantite_restante__gt=0
        ).select_related('produit')
        
        return {
            'stock_total': stock_total,
            'produits_stock': produits_stock,
            'stocks_faibles': stocks_faibles,
            'seuil_stock_faible': seuil_stock_faible,
        }

    # =========================
    # AGENTS SOUS SA RESPONSABILITÉ
    # =========================
    @staticmethod
    def get_agents_superviseur(superviseur):
        """Retourne uniquement les agents terrain sous sa responsabilité"""
        return Agent.objects.filter(
            superviseur=superviseur,
            type_agent='terrain'
        ).select_related('user')

    # =========================
    # PERFORMANCES AGENTS (PÉRIMÈTRE SUPERVISEUR)
    # =========================
    @staticmethod
    def get_performances_agents_superviseur(superviseur):
        agents = SuperviseurDashboardService.get_agents_superviseur(superviseur)
        performances = []

        for agent in agents:
            # VENTES DE CET AGENT (y compris celles de ses stagiaires)
            ventes_agent = Vente.objects.filter(agent=agent)
            
            # Stats globales agent
            stats = ventes_agent.aggregate(
                total_ventes=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')), 
                    Decimal('0')
                ),
                nombre_ventes=Count('id'),
                quantite_vendue=Coalesce(Sum('quantite'), Decimal('0')),
                ventes_gros=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire'), 
                        filter=Q(type_vente='gros')),
                    Decimal('0')
                ),
                ventes_detail=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire'), 
                        filter=Q(type_vente='detail')),
                    Decimal('0')
                ),
                clients_distincts=Count('client', distinct=True)
            )

            # Ventes des stagiaires de cet agent
            ventes_stagiaires = ventes_agent.filter(
                stagiaire__isnull=False
            ).aggregate(
                total_ventes_stagiaires=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')), 
                    Decimal('0')
                ),
                nombre_ventes_stagiaires=Count('id'),
                nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
            )

            total_ventes = stats['total_ventes']
            total_ventes_stagiaires = ventes_stagiaires['total_ventes_stagiaires']
            total_ventes_personnelles = max(
                Decimal('0'), 
                total_ventes - total_ventes_stagiaires
            )

            # DISTRIBUTIONS RÉCENTES à cet agent (30 derniers jours)
            date_debut_recent = timezone.now() - timedelta(days=30)
            distributions_recentes = DistributionAgent.objects.filter(
                agent_terrain=agent,
                superviseur=superviseur,  # Seulement celles faites par ce superviseur
                date_distribution__gte=date_debut_recent
            ).aggregate(
                total_produits=Coalesce(Sum('quantite_totale'), Decimal('0'))
            )

            performances.append({
                'agent': agent,
                'total_ventes': total_ventes,
                'nombre_ventes': stats['nombre_ventes'],
                'quantite_vendue': stats['quantite_vendue'],
                'ventes_gros': stats['ventes_gros'],
                'ventes_detail': stats['ventes_detail'],
                'clients_distincts': stats['clients_distincts'],
                'produits_distribues_recent': distributions_recentes['total_produits'],
                
                # Statistiques stagiaires
                'total_ventes_stagiaires': total_ventes_stagiaires,
                'nombre_ventes_stagiaires': ventes_stagiaires['nombre_ventes_stagiaires'],
                'nombre_stagiaires_distincts': ventes_stagiaires['nombre_stagiaires_distincts'],
                'total_ventes_personnelles': total_ventes_personnelles,
                
                # Propriétés financières
                'total_recouvre': agent.total_recouvre or Decimal('0'),
                'argent_en_possession': agent.argent_en_possession or Decimal('0'),
                'peut_etre_recouvre': agent.peut_etre_recouvre or Decimal('0'),
            })

        return performances

    # =========================
    # VENTES DU SUPERVISEUR LUI-MÊME
    # =========================
    @staticmethod
    def get_ventes_superviseur_personnelles(superviseur):
        """Ventes réalisées personnellement par le superviseur"""
        ventes = Vente.objects.filter(agent=superviseur)

        stats = ventes.aggregate(
            total_ventes=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')), 
                Decimal('0')
            ),
            nombre_ventes=Count('id'),
            quantite_vendue=Coalesce(Sum('quantite'), Decimal('0')),
            ventes_gros=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire'), 
                    filter=Q(type_vente='gros')),
                Decimal('0')
            ),
            ventes_detail=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire'), 
                    filter=Q(type_vente='detail')),
                Decimal('0')
            ),
        )

        # Ventes stagiaires sous la tutelle directe du superviseur
        ventes_stagiaires = ventes.filter(stagiaire__isnull=False).aggregate(
            total_ventes_stagiaires=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')), 
                Decimal('0')
            ),
            nombre_ventes_stagiaires=Count('id'),
            nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
        )

        total_ventes = stats['total_ventes']
        total_ventes_stagiaires = ventes_stagiaires['total_ventes_stagiaires']
        total_ventes_personnelles = max(
            Decimal('0'), 
            total_ventes - total_ventes_stagiaires
        )

        return {
            'total_ventes': total_ventes,
            'total_ventes_personnelles': total_ventes_personnelles,
            'total_ventes_stagiaires': total_ventes_stagiaires,
            'nombre_ventes': stats['nombre_ventes'],
            'quantite_vendue': stats['quantite_vendue'],
            'ventes_gros': stats['ventes_gros'],
            'ventes_detail': stats['ventes_detail'],
            'nombre_ventes_stagiaires': ventes_stagiaires['nombre_ventes_stagiaires'],
            'nombre_stagiaires_distincts': ventes_stagiaires['nombre_stagiaires_distincts'],
        }

    # =========================
    # VENTES GLOBALES DU PÉRIMÈTRE
    # =========================
    @staticmethod
    def get_ventes_perimetre_superviseur(superviseur):
        """
        Ventes du périmètre: superviseur + tous ses agents
        """
        # Agents sous sa responsabilité
        agents_ids = list(
            SuperviseurDashboardService.get_agents_superviseur(superviseur)
            .values_list('id', flat=True)
        )
        agents_ids.append(superviseur.id)  # Ajouter le superviseur lui-même
        
        # Ventes du périmètre
        ventes_perimetre = Vente.objects.filter(agent_id__in=agents_ids)
        
        stats = ventes_perimetre.aggregate(
            total_ventes=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')), 
                Decimal('0')
            ),
            nombre_ventes=Count('id'),
            quantite_vendue=Coalesce(Sum('quantite'), Decimal('0')),
            ventes_gros=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire'), 
                    filter=Q(type_vente='gros')),
                Decimal('0')
            ),
            ventes_detail=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire'), 
                    filter=Q(type_vente='detail')),
                Decimal('0')
            ),
            ventes_credit=Count('id', filter=Q(mode_paiement='credit')),
            ventes_comptant=Count('id', filter=Q(mode_paiement='comptant'))
        )

        # Ventes stagiaires dans le périmètre
        stats_stagiaires = ventes_perimetre.filter(
            stagiaire__isnull=False
        ).aggregate(
            total_ventes_stagiaires=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')), 
                Decimal('0')
            ),
            nombre_ventes_stagiaires=Count('id'),
            nombre_stagiaires_distincts=Count('stagiaire', distinct=True)
        )

        total_ventes = stats['total_ventes']
        total_ventes_stagiaires = stats_stagiaires['total_ventes_stagiaires']
        total_ventes_personnelles = max(
            Decimal('0'), 
            total_ventes - total_ventes_stagiaires
        )

        return {
            'total_ventes': total_ventes,
            'nombre_ventes': stats['nombre_ventes'],
            'quantite_vendue': stats['quantite_vendue'],
            'ventes_gros': stats['ventes_gros'],
            'ventes_detail': stats['ventes_detail'],
            'ventes_credit': stats['ventes_credit'],
            'ventes_comptant': stats['ventes_comptant'],
            'total_ventes_stagiaires': total_ventes_stagiaires,
            'total_ventes_personnelles': total_ventes_personnelles,
            'nombre_ventes_stagiaires': stats_stagiaires['nombre_ventes_stagiaires'],
            'nombre_stagiaires_distincts': stats_stagiaires['nombre_stagiaires_distincts'],
        }

    # =========================
    # VENTES PAR TYPE DANS LE PÉRIMÈTRE
    # =========================
    @staticmethod
    def get_ventes_par_type_perimetre(superviseur):
        """Ventes par type dans le périmètre du superviseur"""
        agents_ids = list(
            SuperviseurDashboardService.get_agents_superviseur(superviseur)
            .values_list('id', flat=True)
        )
        agents_ids.append(superviseur.id)
        
        return Vente.objects.filter(
            agent_id__in=agents_ids
        ).values('type_vente').annotate(
            total=Coalesce(
                Sum(F('quantite') * F('prix_vente_unitaire')), 
                Decimal('0')
            ),
            count=Count('id'),
            quantite=Coalesce(Sum('quantite'), Decimal('0'))
        )

    # =========================
    # DISTRIBUTIONS RÉCENTES DU SUPERVISEUR
    # =========================
    @staticmethod
    def get_distributions_recentes_superviseur(superviseur, jours=30):
        """Distributions récentes faites par ce superviseur"""
        date_debut = timezone.now() - timedelta(days=jours)
        return DistributionAgent.objects.filter(
            superviseur=superviseur,
            date_distribution__gte=date_debut
        ).count()

    # =========================
    # DETTES EN COURS DANS SON PÉRIMÈTRE
    # =========================
    @staticmethod
    def get_dettes_en_cours_perimetre(superviseur):
        """Dettes des agents sous sa supervision + ses propres dettes"""
        # Dettes de ses agents
        dettes_agents = Dette.objects.filter(
            vente__agent__superviseur=superviseur,
            statut__in=['en_cours', 'partiellement_paye']
        ).count()
        
        # Dettes personnelles du superviseur
        dettes_personnelles = Dette.objects.filter(
            vente__agent=superviseur,
            statut__in=['en_cours', 'partiellement_paye']
        ).count()
        
        return dettes_agents + dettes_personnelles

    # =========================
    # STATS FINANCIÈRES DU SUPERVISEUR
    # =========================
    @staticmethod
    def get_stats_financieres_superviseur(superviseur):
        """Statistiques financières du superviseur uniquement"""
        # Recouvrements effectués auprès de ses agents
        total_recouvrements = Recouvrement.objects.filter(
            superviseur=superviseur
        ).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
        )['total']
        
        # Dépenses engagées par ce superviseur
        total_depenses = Depense.objects.filter(
            versement__superviseur=superviseur
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
        
        # Versements bancaires effectués par ce superviseur
        total_versements = VersementBancaire.objects.filter(
            superviseur=superviseur
        ).aggregate(
            total=Coalesce(Sum('montant_vente'), Decimal('0'))
        )['total']
        
        # Dernier versement
        dernier_versement = VersementBancaire.objects.filter(
            superviseur=superviseur
        ).order_by('-date_versement_reelle').first()
        
        # Versements récents
        versements_recents = VersementBancaire.objects.filter(
            superviseur=superviseur
        ).order_by('-date_versement_reelle')[:5]
        
        return {
            'total_recouvrements': total_recouvrements,
            'total_depenses': total_depenses,
            'total_versements': total_versements,
            'solde_actuel': superviseur.solde_vente_superviseur or Decimal('0'),
            'dernier_versement': dernier_versement,
            'versements_recents': versements_recents,
        }

    # =========================
    # RÉCAPITULATIF FINANCIER DU PÉRIMÈTRE
    # =========================
    @staticmethod
    def get_recapitulatif_perimetre(superviseur, performances_agents, ventes_perimetre):
        """Récapitulatif financier du périmètre du superviseur"""
        # Stock attribué au superviseur
        stock_data = SuperviseurDashboardService.get_stock_superviseur(superviseur)
        
        # Total à recouvrer auprès de ses agents
        total_a_recouvrer = sum(
            agent['argent_en_possession'] 
            for agent in performances_agents
        )
        
        # Dettes en cours dans son périmètre
        dettes_en_cours = SuperviseurDashboardService.get_dettes_en_cours_perimetre(
            superviseur
        )
        
        # Calcul des totaux stagiaires
        total_ventes_stagiaires = sum(
            agent['total_ventes_stagiaires'] 
            for agent in performances_agents
        )
        
        total_ventes_personnelles = sum(
            agent['total_ventes_personnelles'] 
            for agent in performances_agents
        )
        
        # Pourcentage ventes stagiaires
        total_ventes = ventes_perimetre['total_ventes']
        total_stagiaires = ventes_perimetre['total_ventes_stagiaires']
        
        pourcentage_ventes_stagiaires = (
            (total_stagiaires / total_ventes * 100)
            if total_ventes > 0 else 0
        )
        
        return {
            'valeur_stock_total': stock_data['stock_total']['total_valeur'],
            'ventes_total': ventes_perimetre['total_ventes'],
            'total_a_recouvrer': total_a_recouvrer,
            'dettes_en_cours_count': dettes_en_cours,
            'total_ventes_stagiaires': total_ventes_stagiaires,
            'total_ventes_personnelles': total_ventes_personnelles,
            'pourcentage_ventes_stagiaires': pourcentage_ventes_stagiaires,
        }

    # =========================
    # BUILD CONTEXT - PÉRIMÈTRE RESTREINT
    # =========================
    @staticmethod
    def build_dashboard_perimetre(user):
        """
        Construit le dashboard avec uniquement le périmètre du superviseur
        """
        superviseur = SuperviseurDashboardService.get_superviseur(user)
        if not superviseur:
            return None

        # 1. Stock attribué au superviseur
        stock_data = SuperviseurDashboardService.get_stock_superviseur(superviseur)
        
        # 2. Agents sous sa responsabilité
        agents_superviseur = SuperviseurDashboardService.get_agents_superviseur(
            superviseur
        )
        
        # 3. Performances de ses agents
        performances_agents = SuperviseurDashboardService.get_performances_agents_superviseur(
            superviseur
        )
        
        # 4. Ventes personnelles du superviseur
        ventes_superviseur = SuperviseurDashboardService.get_ventes_superviseur_personnelles(
            superviseur
        )
        
        # 5. Ventes globales du périmètre (superviseur + agents)
        ventes_perimetre = SuperviseurDashboardService.get_ventes_perimetre_superviseur(
            superviseur
        )
        
        # 6. Ventes par type dans le périmètre
        ventes_par_type = SuperviseurDashboardService.get_ventes_par_type_perimetre(
            superviseur
        )
        
        # 7. Statistiques financières du superviseur
        stats_superviseur = SuperviseurDashboardService.get_stats_financieres_superviseur(
            superviseur
        )
        
        # 8. Distributions récentes
        distributions_superviseur = SuperviseurDashboardService.get_distributions_recentes_superviseur(
            superviseur
        )
        
        # 9. Dettes en cours dans le périmètre
        dettes_en_cours = SuperviseurDashboardService.get_dettes_en_cours_perimetre(
            superviseur
        )
        
        # 10. Récapitulatif financier du périmètre
        recapitulatif_financier = SuperviseurDashboardService.get_recapitulatif_perimetre(
            superviseur, performances_agents, ventes_perimetre
        )

        context = {
            'superviseur': superviseur,
            
            # Stock attribué
            'stock_total': stock_data['stock_total'],
            'produits_stock': stock_data['produits_stock'],
            'stocks_faibles': stock_data['stocks_faibles'],
            'seuil_stock_faible': stock_data['seuil_stock_faible'],
            
            # Agents et leurs performances
            'agents_terrain': agents_superviseur,
            'performances_agents': performances_agents,
            
            # Ventes personnelles du superviseur
            'ventes_superviseur': ventes_superviseur,
            
            # Ventes globales du périmètre (renommé pour compatibilité template)
            'ventes_global': ventes_perimetre,
            
            # Ventes par type dans le périmètre
            'ventes_par_type': list(ventes_par_type),
            
            # Finances du superviseur
            'stats_superviseur': stats_superviseur,
            
            # Distributions récentes
            'distributions_superviseur': distributions_superviseur,
            
            # Dettes en cours
            'dettes_en_cours': dettes_en_cours,
            
            # Récapitulatif financier
            'recapitulatif_financier': recapitulatif_financier,
            
            # Suppression des vérifications de cohérence globale
            # car on ne compare plus avec les données globales de l'entreprise
        }

        return context