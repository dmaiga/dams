# core/services/dashboard_service.py
from django.utils import timezone
from django.db.models import Sum, Count, Q, F, FloatField
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from datetime import timedelta, datetime
from decimal import Decimal
import calendar

from core.models import (
    Vente, LotEntrepot, Perte, Depense, VersementBancaire,
    Agent, Dette, Recouvrement, PaiementDette, 
    DetailDistribution, Client, Produit
)

class DashboardService:

    @staticmethod
    def get_kpis_fournisseurs(periode_type='annee', annee=None, mois=None):
        """
        KPIs fournisseurs – LOGIQUE SAINE
        - Dette contractuelle = réceptions (lots)
        - Dette consommée = ventes (bornée)
        - Paiement = comparé au contractuel UNIQUEMENT
        """
    
        from core.models import Fournisseur, Vente, PaiementFournisseur, LotEntrepot
        from django.db.models import Sum, F
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
    
        fournisseurs = Fournisseur.objects.filter(
            lots__isnull=False
        ).distinct().order_by('nom')
    
        for fournisseur in fournisseurs:
        
            # =========================
            # 1️⃣ DETTE CONTRACTUELLE (LOTS)
            # =========================
            dette_contractuelle = LotEntrepot.objects.filter(
                fournisseur=fournisseur,
                date_reception__lte=date_fin
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite_initiale') * F('prix_achat_unitaire')),
                    Decimal('0.00')
                )
            )['total']
    
            # =========================
            # 2️⃣ DETTE CONSOMMÉE (VENTES)
            # =========================
            dette_consommee_brute = Vente.objects.filter(
                detail_distribution__lot__fournisseur=fournisseur,
                date_vente__lte=now
            ).aggregate(
                total=Coalesce(
                    Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')),
                    Decimal('0.00')
                )
            )['total']
    
            dette_consommee = min(dette_consommee_brute, dette_contractuelle)
    
            # =========================
            # 3️⃣ PAIEMENTS
            # =========================
            total_paye = PaiementFournisseur.objects.filter(
                fournisseur=fournisseur,
                est_supprime=False,
                date_paiement__lte=now
            ).aggregate(
                total=Coalesce(Sum('montant'), Decimal('0.00'))
            )['total']
    
            # =========================
            # 4️⃣ RESTE CONTRACTUEL
            # =========================
            reste_contractuel = max(
                dette_contractuelle - total_paye,
                Decimal('0.00')
            )
    
            pourcentage_paye = (
                (total_paye / dette_contractuelle) * 100
                if dette_contractuelle > 0 else 100
            )
    
            # =========================
            # 5️⃣ LOTS DE LA PÉRIODE
            # =========================
            nombre_lots_periode = fournisseur.lots.filter(
                date_reception__range=[date_debut, date_fin]
            ).count()
    
            fournisseurs_data.append({
                'fournisseur': fournisseur,
                'nom': fournisseur.nom,
    
                # DETTES
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
    
                # FINANCIER
                'total_paye': total_paye,
                'reste_contractuel': reste_contractuel,
                'pourcentage_paye': round(pourcentage_paye, 2),
    
                # META
                'nombre_lots_periode': nombre_lots_periode,
                'total_lots': fournisseur.lots.count(),
            })
    
            # =========================
            # AGRÉGATS GLOBAUX
            # =========================
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
    
            # KPI GLOBAUX
            'dette_contractuelle': total_dette_contractuelle,
            'dette_consommee': total_dette_consommee,
            'total_paye': total_paye_global,
            'reste_contractuel': total_reste_contractuel,
            'pourcentage_global_paye': round(pourcentage_global_paye, 2),
    
            'nombre_fournisseurs': len(fournisseurs_data),
        }
    
    @staticmethod
    def get_agents_inactifs(depuis_jours=3):
        """Retourne la liste des agents qui n'ont pas fait de ventes depuis X jours."""
        seuil = timezone.now() - timedelta(days=depuis_jours)
    
        agents = Agent.objects.filter(type_agent__in=["terrain", "entrepot"])
        agents_inactifs = []
    
        for agent in agents:
            # Dernière vente
            derniere_vente = (
                Vente.objects.filter(agent=agent)
                .order_by('-date_vente')
                .first()
            )
    
            if derniere_vente:
                if derniere_vente.date_vente < seuil:
                    agents_inactifs.append({
                        "nom": agent.full_name,
                        "jours_depuis": (timezone.now() - derniere_vente.date_vente).days,
                        "derniere_vente": derniere_vente.date_vente,
                    })
            else:
                # Aucun historique de vente
                agents_inactifs.append({
                    "nom": agent.full_name,
                    "jours_depuis": None,
                    "derniere_vente": None,
                })
    
        # Trier : ceux sans ventes d'abord, puis les plus anciens
        agents_inactifs.sort(key=lambda x: (x["jours_depuis"] is not None, x["jours_depuis"]))
        return agents_inactifs
    
    
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
        """🔵 Bloc 1 : KPIs immédiats avec filtres de période"""
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        
        # Filtres de période pour les différentes données
        filtre_ventes = Q(date_vente__range=[date_debut, date_fin])
        filtre_pertes = Q(date_perte__range=[date_debut, date_fin])
        filtre_depenses = Q(date_depense__range=[date_debut, date_fin])
        
        # Total ventes de la période
        ventes_periode = Vente.objects.filter(filtre_ventes)
        total_ventes_periode = sum(
            float(vente.quantite * vente.prix_vente_unitaire) 
            for vente in ventes_periode
        )
        
        # Stock total (en CFA) - TOUJOURS calculé sur l'état actuel
        lots = LotEntrepot.objects.all()
        stock_total = sum(float(lot.valeur_actuelle_stock) for lot in lots)
        
        # Valeur des pertes de la période
        pertes_periode = Perte.objects.filter(filtre_pertes).select_related('lot')
        valeur_pertes = sum(
            float(perte.quantite_perdue * perte.lot.prix_achat_unitaire) 
            for perte in pertes_periode
        )
        
        # Solde des superviseurs - TOUJOURS calculé sur l'état actuel
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        solde_superviseurs = sum(float(superviseur.solde_reel_superviseur) for superviseur in superviseurs)
        
        # Dépenses totales (période)
        depenses_periode = Depense.objects.filter(filtre_depenses)
        total_depenses = sum(float(depense.montant) for depense in depenses_periode)
        
        # Marge brute de la période
        marge_brute_periode = DashboardService.calculer_marge_brute_periode(date_debut, date_fin)
        
        # Calcul du Cash Flow (CA - Dépenses)
        cash_flow = total_ventes_periode - total_depenses
        
        return {
            'total_ventes_periode': total_ventes_periode,
            'stock_total': stock_total,
            'valeur_pertes': valeur_pertes,
            'solde_superviseurs': solde_superviseurs,
            'total_depenses': total_depenses,
            'marge_brute_periode': marge_brute_periode,
            'cash_flow': cash_flow,
            'nombre_ventes_periode': ventes_periode.count(),
            'date_debut': date_debut,
            'date_fin': date_fin,
            'periode_type': periode_type
        }

    @staticmethod
    def calculer_marge_brute_periode(date_debut, date_fin):
        """Calcule la marge brute réelle pour une période donnée"""
        ventes_periode = Vente.objects.filter(
            date_vente__range=[date_debut, date_fin]
        ).select_related('detail_distribution__lot')
        
        marge_totale = 0
        for vente in ventes_periode:
            if vente.detail_distribution and vente.detail_distribution.lot:
                prix_achat = float(vente.detail_distribution.lot.prix_achat_unitaire)
                prix_vente = float(vente.prix_vente_unitaire)
                quantite = float(vente.quantite)
                
                marge_totale += quantite * (prix_vente - prix_achat)
        
        return marge_totale

    @staticmethod
    def get_stock_essentiel():
        """🟣 Bloc 2 : Stock essentiel - Données utiles (toujours actuel)"""
        stocks = []
        
        lots = LotEntrepot.objects.select_related('produit').filter(quantite_restante__gt=0)
        
        for lot in lots:
            quantite_restante = float(lot.quantite_restante)
            valeur_actuelle = float(lot.valeur_actuelle_stock)
            
            # Calcul du taux de rotation (ventes du produit / stock actuel)
            ventes_produit = Vente.objects.filter(
                detail_distribution__lot__produit=lot.produit,
                date_vente__gte=timezone.now() - timedelta(days=30)
            )
            quantite_vendue_mois = sum(float(v.quantite) for v in ventes_produit)
            
            taux_rotation = (quantite_vendue_mois / quantite_restante * 100) if quantite_restante > 0 else 0
            
            stocks.append({
                'produit': lot.produit.nom,
                'quantite_restante': quantite_restante,
                'valeur_actuelle': valeur_actuelle,
                'taux_rotation': taux_rotation,
                'ventes_30j': quantite_vendue_mois
            })
        
        # Trier par valeur actuelle décroissante
        return sorted(stocks, key=lambda x: x['valeur_actuelle'], reverse=True)

    @staticmethod
    def get_performances_agents(periode_type='mois', annee=None, mois=None):
        """🟠 Bloc 3 : Performances des Agents avec filtre de période"""
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        
        performances = []
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        
        for superviseur in superviseurs:
            # Ventes de la période
            ventes_periode = Vente.objects.filter(
                agent=superviseur,
                date_vente__range=[date_debut, date_fin]
            )
            total_ventes_periode = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_periode)
            
            # Recouvrements de la période
            recouvrements_periode = Recouvrement.objects.filter(
                superviseur=superviseur,
                date_recouvrement__range=[date_debut, date_fin]
            )
            total_recouvre_periode = sum(float(r.montant_recouvre) for r in recouvrements_periode)
            
            performances.append({
                'superviseur': superviseur.full_name,
                'total_ventes': total_ventes_periode,
                'total_recouvre': total_recouvre_periode,
                'solde_actuel': float(superviseur.solde_reel_superviseur),  # Toujours actuel
                'moyenne_vente': total_ventes_periode / max(ventes_periode.count(), 1),
                
            })
        
        # Trier par CA décroissant
        return sorted(performances, key=lambda x: x['total_ventes'], reverse=True)
    
    @staticmethod
    def get_analyses_ventes_avancees(periode_type='mois', annee=None, mois=None):
        """🔴 Bloc 4 : Analyses Ventes Avancées avec filtre de période"""
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        
        # Top 10 produits par CA pour la période
        produits_data = {}
        ventes_periode = Vente.objects.filter(
            date_vente__range=[date_debut, date_fin]
        ).select_related('detail_distribution__lot__produit')
        
        for vente in ventes_periode:
            if (vente.detail_distribution and 
                vente.detail_distribution.lot and 
                vente.detail_distribution.lot.produit):
                
                produit_nom = vente.detail_distribution.lot.produit.nom
                if produit_nom not in produits_data:
                    produits_data[produit_nom] = {
                        'quantite': 0,
                        'ca': 0,
                        'marge': 0,
                        'ventes_gros': 0,
                        'ventes_detail': 0
                    }
                
                quantite_vendue = float(vente.quantite)
                prix_vente = float(vente.prix_vente_unitaire)
                prix_achat = float(vente.detail_distribution.lot.prix_achat_unitaire)
                
                produits_data[produit_nom]['quantite'] += quantite_vendue
                produits_data[produit_nom]['ca'] += quantite_vendue * prix_vente
                produits_data[produit_nom]['marge'] += quantite_vendue * (prix_vente - prix_achat)
                
                # Répartition par type de vente
                if vente.type_vente == 'gros':
                    produits_data[produit_nom]['ventes_gros'] += quantite_vendue
                else:
                    produits_data[produit_nom]['ventes_detail'] += quantite_vendue
        
        top_produits = sorted(
            [{'nom': k, **v} for k, v in produits_data.items()],
            key=lambda x: x['ca'],
            reverse=True
        )[:10]
        
        # Répartition détaillée type de vente
        ventes_gros = ventes_periode.filter(type_vente='gros')
        ventes_detail = ventes_periode.filter(type_vente='detail')
        
        ca_gros = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_gros)
        ca_detail = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_detail)
        
        # Répartition mode paiement
        ventes_comptant = ventes_periode.filter(mode_paiement='comptant')
        ventes_credit = ventes_periode.filter(mode_paiement='credit')
        
        ca_comptant = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_comptant)
        ca_credit = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_credit)
        
        # Tendance des ventes selon la période
        if periode_type == 'annee':
            # Tendance mensuelle pour l'année
            tendance = []
            for i in range(1, 13):
                mois_debut = datetime(annee, i, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
                dernier_jour = calendar.monthrange(annee, i)[1]
                mois_fin = datetime(annee, i, dernier_jour, 23, 59, 59, tzinfo=timezone.get_current_timezone())
                
                ventes_mois = Vente.objects.filter(date_vente__range=[mois_debut, mois_fin])
                ca_mois = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_mois)
                
                tendance.append({
                    'periode': calendar.month_name[i],
                    'ca': ca_mois,
                    'ventes': ventes_mois.count()
                })
        else:
            # Tendance des 30 derniers jours pour le mois
            tendance = []
            for i in range(30):
                date_jour = date_fin - timedelta(days=29-i)
                ventes_jour = Vente.objects.filter(date_vente__date=date_jour.date())
                ca_jour = sum(float(v.quantite * v.prix_vente_unitaire) for v in ventes_jour)
                
                tendance.append({
                    'periode': date_jour.strftime('%d/%m'),
                    'ca': ca_jour,
                    'ventes': ventes_jour.count()
                })
        
        return {
            'top_produits': top_produits,
            'repartition_type': {
                'gros': {'ca': ca_gros, 'ventes': ventes_gros.count(), 'pourcentage': (ca_gros/(ca_gros+ca_detail)*100) if (ca_gros+ca_detail) > 0 else 0},
                'detail': {'ca': ca_detail, 'ventes': ventes_detail.count(), 'pourcentage': (ca_detail/(ca_gros+ca_detail)*100) if (ca_gros+ca_detail) > 0 else 0}
            },
            'repartition_paiement': {
                'comptant': {'ca': ca_comptant, 'ventes': ventes_comptant.count(), 'pourcentage': (ca_comptant/(ca_comptant+ca_credit)*100) if (ca_comptant+ca_credit) > 0 else 0},
                'credit': {'ca': ca_credit, 'ventes': ventes_credit.count(), 'pourcentage': (ca_credit/(ca_comptant+ca_credit)*100) if (ca_comptant+ca_credit) > 0 else 0}
            },
            'tendance_ventes': tendance,
            'total_ca_periode': ca_gros + ca_detail
        }
    
    @staticmethod
    def get_analyses_depenses(periode_type='mois', annee=None, mois=None):
        """🟢 Bloc 5 : Analyses des Dépenses avec filtre de période"""
        date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)
        
        # Dépenses totales de la période
        depenses_periode = Depense.objects.filter(date_depense__range=[date_debut, date_fin])
        total_depenses_periode = sum(float(d.montant) for d in depenses_periode)
        
        # Dépenses par superviseur pour la période
        depenses_par_superviseur = []
        for agent in Agent.objects.filter(type_agent='entrepot'):
            depenses_agent = Depense.objects.filter(
                versement__superviseur=agent, 
                date_depense__range=[date_debut, date_fin]
            )
            total_depenses_agent = sum(float(d.montant) for d in depenses_agent)
            
            depenses_par_superviseur.append({
                'superviseur': agent.full_name,
                'total_depenses': total_depenses_agent,
                'nombre_depenses': depenses_agent.count()
            })
        
        # Évolution des dépenses selon la période
        if periode_type == 'annee':
            # Évolution sur les 12 derniers mois
            evolution = []
            for i in range(12):
                mois_ref = date_fin - timedelta(days=30*i)
                annee_ref = mois_ref.year
                mois_num = mois_ref.month
                
                debut_mois_ref = datetime(annee_ref, mois_num, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
                dernier_jour = calendar.monthrange(annee_ref, mois_num)[1]
                fin_mois_ref = datetime(annee_ref, mois_num, dernier_jour, 23, 59, 59, tzinfo=timezone.get_current_timezone())
                
                depenses_mois_ref = Depense.objects.filter(date_depense__range=[debut_mois_ref, fin_mois_ref])
                total_depenses_mois_ref = sum(float(d.montant) for d in depenses_mois_ref)
                
                evolution.append({
                    'periode': debut_mois_ref.strftime('%b %Y'),
                    'montant': total_depenses_mois_ref
                })
        else:
            # Évolution sur les 6 derniers mois
            evolution = []
            for i in range(6):
                mois_ref = date_fin - timedelta(days=30*i)
                annee_ref = mois_ref.year
                mois_num = mois_ref.month
                
                debut_mois_ref = datetime(annee_ref, mois_num, 1, 0, 0, 0, tzinfo=timezone.get_current_timezone())
                dernier_jour = calendar.monthrange(annee_ref, mois_num)[1]
                fin_mois_ref = datetime(annee_ref, mois_num, dernier_jour, 23, 59, 59, tzinfo=timezone.get_current_timezone())
                
                depenses_mois_ref = Depense.objects.filter(date_depense__range=[debut_mois_ref, fin_mois_ref])
                total_depenses_mois_ref = sum(float(d.montant) for d in depenses_mois_ref)
                
                evolution.append({
                    'periode': debut_mois_ref.strftime('%b %Y'),
                    'montant': total_depenses_mois_ref
                })
        
        evolution.reverse()
        
        return {
            'total_depenses_periode': total_depenses_periode,
            'depenses_par_superviseur': depenses_par_superviseur,
            'evolution_depenses': evolution
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
    
    @staticmethod
    def get_portefeuille_superviseur(superviseur_id, periode_type='mois', annee=None, mois=None):
        """Retourne les informations financières d'un superviseur spécifique (valeurs limitées à la période).
        Les clés renvoyées correspondent au template : total_recouvre_periode, total_depenses_periode, total_versements_periode.
        """
        try:
            superviseur = Agent.objects.get(id=superviseur_id, type_agent='entrepot')
            date_debut, date_fin = DashboardService.get_periodes(periode_type, annee, mois)

            # Recouvrements effectués par le superviseur (période)
            recouvrements_qs = Recouvrement.objects.filter(
                superviseur=superviseur,
                date_recouvrement__range=[date_debut, date_fin]
            )
            total_recouvre_periode = recouvrements_qs.aggregate(
                total=Coalesce(Sum('montant_recouvre'), Decimal('0.00'))
            )['total'] or Decimal('0.00')

            # Dépenses rattachées aux versements du superviseur (période)
            depenses_qs = Depense.objects.filter(
                versement__superviseur=superviseur,
                date_depense__range=[date_debut, date_fin]
            )
            total_depenses_periode = depenses_qs.aggregate(
                total=Coalesce(Sum('montant'), Decimal('0.00'))
            )['total'] or Decimal('0.00')

            # Versements bancaires (période) -> somme des montants (vente + hors_vente)
            versements_qs = VersementBancaire.objects.filter(
                superviseur=superviseur,
                date_versement_reelle__range=[date_debut, date_fin]
            )

            # On calcule total des versements en Python (sûr et simple)
            total_versements_periode = sum(
                (v.montant_vente or Decimal('0.00')) + (v.montant_hors_vente or Decimal('0.00'))
                for v in versements_qs
            ) if versements_qs.exists() else Decimal('0.00')

            # Ventes personnelles de la période (si besoin)
            ventes_personnelles_qs = Vente.objects.filter(
                agent=superviseur,
                date_vente__range=[date_debut, date_fin],
                stagiaire__isnull=True
            )
            total_ventes_personnelles = ventes_personnelles_qs.aggregate(
                total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0.00'))
            )['total'] or Decimal('0.00')

            # Solde actuel (propriété calculée sur l'état actuel de l'agent)
            solde_actuel = float(superviseur.solde_reel_superviseur)

            return {
                'superviseur': superviseur.full_name,
                'superviseur_id': superviseur.id,
                'total_recouvre_periode': total_recouvre_periode,
                'total_depenses_periode': total_depenses_periode,
                'total_versements_periode': total_versements_periode,
                'total_ventes_personnelles': total_ventes_personnelles,
                'solde_actuel': solde_actuel,
                'nombre_recouvrements': recouvrements_qs.count(),
                'nombre_depenses': depenses_qs.count(),
                'nombre_versements': versements_qs.count(),
                'recouvrements_recentes': list(recouvrements_qs.order_by('-date_recouvrement')[:5]),
                'depenses_recentes': list(depenses_qs.order_by('-date_depense')[:5]),
                'versements_recents': list(versements_qs.order_by('-date_versement_reelle')[:5])
            }
        except Agent.DoesNotExist:
            return None


    @staticmethod
    def get_portefeuilles_tous_superviseurs(periode_type='mois', annee=None, mois=None):
        """Retourne les portefeuilles de TOUS les superviseurs (pour la direction) avec valeurs sur la période."""
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        portefeuilles = []

        for superviseur in superviseurs:
            portefeuille = DashboardService.get_portefeuille_superviseur(
                superviseur.id, periode_type, annee, mois
            )
            if portefeuille:
                portefeuilles.append(portefeuille)

        # Trier par solde actuel décroissant (valeur instantanée)
        return sorted(portefeuilles, key=lambda x: x.get('solde_actuel', 0), reverse=True)

    @staticmethod
    def get_stock_essentiel_avec_fournisseurs():
        """Stock essentiel avec informations fournisseurs et statut amélioré"""
        stocks = []
        
        lots = LotEntrepot.objects.select_related('produit', 'fournisseur').filter(quantite_restante__gt=0)
        
        for lot in lots:
            quantite_restante = float(lot.quantite_restante)
            valeur_actuelle = float(lot.valeur_actuelle_stock)
            
            # Calcul du taux de rotation
            ventes_produit = Vente.objects.filter(
                detail_distribution__lot__produit=lot.produit,
                date_vente__gte=timezone.now() - timedelta(days=30)
            )
            quantite_vendue_mois = sum(float(v.quantite) for v in ventes_produit)
            
            taux_rotation = (quantite_vendue_mois / quantite_restante * 100) if quantite_restante > 0 else 0
            
            # Calcul des jours de stock
            jours_stock = (quantite_restante / (quantite_vendue_mois / 30)) if quantite_vendue_mois > 0 else 999
            
            # Détermination du statut amélioré
            statut, badge_class, description = DashboardService.determiner_statut_stock(
                taux_rotation, jours_stock, quantite_restante
            )
            
            stocks.append({
                'produit': lot.produit.nom,
                'fournisseur': lot.fournisseur.nom if lot.fournisseur else "Non spécifié",
                'quantite_restante': quantite_restante,
                'valeur_actuelle': valeur_actuelle,
                'taux_rotation': taux_rotation,
                'ventes_30j': quantite_vendue_mois,
                'jours_stock': jours_stock,
                'prix_achat_unitaire': float(lot.prix_achat_unitaire),
                'date_reception': lot.date_reception,
                'reference_lot': lot.reference_lot or "N/A",
                'statut': statut,
                'badge_class': badge_class,
                'statut_description': description
            })
        
        return sorted(stocks, key=lambda x: x['valeur_actuelle'], reverse=True)

    @staticmethod
    def determiner_statut_stock(taux_rotation, jours_stock, quantite_restante):
        """Détermine le statut du stock basé sur 3 critères"""
        
        # CRITÈRE 1 : Rotation (dynamique du produit)
        if taux_rotation > 150:  # Rotation très élevée
            critere_rotation = 3
        elif taux_rotation > 80:  # Bonne rotation
            critere_rotation = 2
        elif taux_rotation > 30:  # Rotation moyenne
            critere_rotation = 1
        else:  # Faible rotation
            critere_rotation = 0

        # CRITÈRE 2 : Jours de stock (risque de rupture)
        if jours_stock < 7:  # Risque de rupture imminent
            critere_jours = 0
        elif jours_stock < 15:  # Stock faible
            critere_jours = 1
        elif jours_stock < 30:  # Stock correct
            critere_jours = 2
        else:  # Stock élevé (risque de surstock)
            critere_jours = 3

        # CRITÈRE 3 : Quantité restante (volume physique)
        if quantite_restante < 10:  # Quantité très faible
            critere_quantite = 0
        elif quantite_restante < 50:  # Quantité faible
            critere_quantite = 1
        elif quantite_restante < 200:  # Quantité moyenne
            critere_quantite = 2
        else:  # Quantité élevée
            critere_quantite = 3

        # Score total (0-9)
        score_total = critere_rotation + critere_jours + critere_quantite

        # Détermination du statut final
        if score_total >= 7:
            return "optimal", "badge-success", "Stock optimal - Rotation élevée, niveau approprié"
        elif score_total >= 5:
            return "correct", "badge-info", "Stock correct - Équilibre acceptable"
        elif score_total >= 3:
            return "attention", "badge-warning", "Attention nécessaire - Surveiller le stock"
        else:
            return "critique", "badge-error", "Action requise - Risque élevé"