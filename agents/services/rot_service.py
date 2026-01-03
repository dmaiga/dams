# agents/services/rot_service.py
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, F, Q, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from collections import defaultdict

from core.models import (
    Agent, Vente, DistributionAgent,
    LotEntrepot, Dette, Recouvrement,
    VersementBancaire, Depense, Fournisseur,
    PaiementFournisseur, FactureLotEntrepot,
    Client, Produit
)


class RotDashboardService:
    """
    Service pour le dashboard ROT (Responsable Opérations et Trésorerie)
    Gère le flux financier : fournisseurs, superviseurs, versements bancaires
    """

    @staticmethod
    def get_rot(user):
        """Vérifie si l'utilisateur est un ROT"""
        try:
            return Agent.objects.get(
                user=user,
                type_agent='rot'
            )
        except Agent.DoesNotExist:
            return None

    # =========================
    # CALCUL DU SOLDE SUPERVISEUR (remplace la propriété)
    # =========================
    @staticmethod
    def calculer_solde_superviseur(superviseur):
        """Calcule le solde d'un superviseur (remplace solde_vente_superviseur)"""
        if not superviseur or superviseur.type_agent != 'entrepot':
            return Decimal('0')
        
        # 1. RECOUVREMENTS effectués par le superviseur
        recouvrements = Recouvrement.objects.filter(superviseur=superviseur).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
        )['total']
        
        # 2. VENTES personnelles du superviseur
        ventes_personnelles = Vente.objects.filter(agent=superviseur).aggregate(
            total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
        )['total']
        
        # 3. VERSEMENTS effectués par le superviseur
        versements = VersementBancaire.objects.filter(superviseur=superviseur).aggregate(
            total=Coalesce(Sum('montant_vente'), Decimal('0'))
        )['total']
        
        # 4. DÉPENSES du superviseur
        depenses = Depense.objects.filter(versement__superviseur=superviseur).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
        
        # 5. AJUSTEMENT MANUEL
        ajustement = superviseur.ajustement_solde or Decimal('0')
        
        # Calcul du solde
        entrees = recouvrements + ventes_personnelles
        sorties = versements + depenses
        solde = entrees - sorties + ajustement
        
        return solde

    # =========================
    # VUE FINANCIÈRE GLOBALE
    # =========================
    @staticmethod
    def get_vue_financiere_globale():
        """Vue financière complète de l'entreprise"""
        # 1. VENTES TOTALES
        ventes_total = Vente.objects.aggregate(
            total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
        )['total']
        
        # 2. STOCK TOTAL (valeur)
        stock_total = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).aggregate(
            total_valeur=Coalesce(
                Sum(F('quantite_restante') * F('prix_achat_unitaire')), 
                Decimal('0')
            )
        )['total_valeur']
        
        # 3. ARGENT À RECOUVRER (total agents + superviseurs)
        agents_terrain = Agent.objects.filter(type_agent='terrain')
        argent_a_recouvrer = Decimal('0')
        for agent in agents_terrain:
            argent_a_recouvrer += agent.argent_en_possession or Decimal('0')
        
        # 4. VERSEMENTS BANCAIRES TOTAUX
        versements_totaux = VersementBancaire.objects.aggregate(
            total=Coalesce(Sum('montant_vente'), Decimal('0'))
        )['total']
        
        # 5. DÉPENSES TOTALES
        depenses_total = Depense.objects.aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
        
        # 6. FLUX NET (entrées - sorties)
        flux_net = ventes_total - versements_totaux - depenses_total
        
        return {
            'ventes_total': ventes_total,
            'stock_total_valeur': stock_total,
            'argent_a_recouvrer_total': argent_a_recouvrer,
            'versements_totaux': versements_totaux,
            'depenses_total': depenses_total,
            'flux_net': flux_net,
            'liquidite_disponible': flux_net  # Approximation
        }

    # =========================
    # GESTION FOURNISSEURS
    # =========================
    @staticmethod
    def get_situation_fournisseurs():
        """Situation financière avec les fournisseurs"""
        fournisseurs = Fournisseur.objects.all()
        data = []
        
        for fournisseur in fournisseurs:
            # Dette contractuelle (montant total des lots)
            dette_contractuelle = fournisseur.dette_contractuelle or Decimal('0')
            
            # Dette consommée (produits vendus)
            dette_consommee = fournisseur.dette_consomme or Decimal('0')
            
            # Paiements effectués
            paiements = fournisseur.total_paye or Decimal('0')
            
            # Dette restante
            dette_restante = max(Decimal('0'), dette_consommee - paiements)
            
            # Stock actuel de ce fournisseur
            stock_fournisseur = LotEntrepot.objects.filter(
                fournisseur=fournisseur,
                quantite_restante__gt=0
            ).aggregate(
                valeur=Coalesce(
                    Sum(F('quantite_restante') * F('prix_achat_unitaire')), 
                    Decimal('0')
                )
            )['valeur']
            
            # Alertes
            alerte_dette = dette_restante > Decimal('100000')  # Seuil 100,000 FCFA
            alerte_paiement = paiements < (dette_consommee * Decimal('0.5'))  # Moins de 50% payé
            
            data.append({
                'fournisseur': fournisseur,
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
                'paiements_effectues': paiements,
                'dette_restante': dette_restante,
                'stock_actuel': stock_fournisseur,
                'alerte_dette': alerte_dette,
                'alerte_paiement': alerte_paiement,
                'taux_paiement': (paiements / dette_consommee * 100) if dette_consommee > 0 else 0,
            })
        
        # Totaux
        total_dette_restante = sum(item['dette_restante'] for item in data)
        total_paiements = sum(item['paiements_effectues'] for item in data)
        total_stock = sum(item['stock_actuel'] for item in data)
        
        return {
            'fournisseurs': data,
            'totaux': {
                'dette_restante_total': total_dette_restante,
                'paiements_total': total_paiements,
                'stock_total': total_stock,
                'nombre_fournisseurs': len(data),
                'fournisseurs_alertes': sum(1 for f in data if f['alerte_dette'] or f['alerte_paiement'])
            }
        }

    # =========================
    # GESTION SUPERVISEURS (CORRIGÉ)
    # =========================
    @staticmethod
    def get_situation_superviseurs():
        """Situation financière avec les superviseurs"""
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        data = []
        
        for superviseur in superviseurs:
            # 1. RECOUVREMENTS effectués auprès de ses agents
            recouvrements_superviseur = Recouvrement.objects.filter(
                superviseur=superviseur
            ).aggregate(
                total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
            )['total']
            
            # 2. VENTES personnelles du superviseur
            ventes_personnelles = Vente.objects.filter(agent=superviseur).aggregate(
                total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
            )['total']
            
            # 3. ARGENT ENTRANT TOTAL (recouvrements + ventes personnelles)
            argent_entrant = recouvrements_superviseur + ventes_personnelles
            
            # 4. VERSEMENTS effectués par le superviseur
            versements_superviseur = VersementBancaire.objects.filter(
                superviseur=superviseur
            ).aggregate(
                total=Coalesce(Sum('montant_vente'), Decimal('0'))
            )['total']
            
            # 5. DÉPENSES du superviseur
            depenses_superviseur = Depense.objects.filter(
                versement__superviseur=superviseur
            ).aggregate(
                total=Coalesce(Sum('montant'), Decimal('0'))
            )['total']
            
            # 6. SOLDE actuel (utilise la méthode statique)
            solde_actuel = RotDashboardService.calculer_solde_superviseur(superviseur)
            
            # 7. ARGENT À RECOUVRER auprès de ses agents
            agents_superviseur = Agent.objects.filter(
                superviseur=superviseur, 
                type_agent='terrain'
            )
            argent_a_recouvrer = Decimal('0')
            for agent in agents_superviseur:
                argent_a_recouvrer += agent.argent_en_possession or Decimal('0')
            
            # 8. DERNIER VERSEMENT
            dernier_versement = VersementBancaire.objects.filter(
                superviseur=superviseur
            ).order_by('-date_versement_reelle').first()
            
            # 9. STATUT
            statut = "en_regle" if solde_actuel >= 0 else "en_defaut"
            alerte = solde_actuel < Decimal('-50000')  # Seuil -50,000 FCFA
            
            # 10. Jours sans versement
            jours_sans_versement = 999
            if dernier_versement:
                jours_sans_versement = (timezone.now().date() - dernier_versement.date_versement_reelle.date()).days
            
            data.append({
                'superviseur': superviseur,
                'recouvrements': recouvrements_superviseur,
                'ventes_personnelles': ventes_personnelles,
                'argent_entrant_total': argent_entrant,
                'versements': versements_superviseur,
                'depenses': depenses_superviseur,
                'solde_actuel': solde_actuel,
                'argent_a_recouvrer': argent_a_recouvrer,
                'dernier_versement': dernier_versement,
                'nombre_agents': agents_superviseur.count(),
                'statut': statut,
                'alerte': alerte,
                'jours_sans_versement': jours_sans_versement,
            })
        
        # Totaux
        total_solde = sum(item['solde_actuel'] for item in data)
        total_argent_recouvrer = sum(item['argent_a_recouvrer'] for item in data)
        total_versements = sum(item['versements'] for item in data)
        
        return {
            'superviseurs': data,
            'totaux': {
                'solde_total': total_solde,
                'argent_a_recouvrer_total': total_argent_recouvrer,
                'versements_total': total_versements,
                'nombre_superviseurs': len(data),
                'superviseurs_alertes': sum(1 for s in data if s['alerte']),
                'superviseurs_en_regle': sum(1 for s in data if s['statut'] == 'en_regle')
            }
        }

    # =========================
    # FLUX TRÉSORERIE (CORRIGÉ)
    # =========================
    @staticmethod
    def get_flux_tresorerie_periode(jours=30):
        """Flux de trésorerie sur une période"""
        date_debut = timezone.now() - timedelta(days=jours)
        
        # ENTRÉES
        entree_recouvrements = Recouvrement.objects.filter(
            date_recouvrement__gte=date_debut
        ).aggregate(
            total=Coalesce(Sum('montant_recouvre'), Decimal('0'))
        )['total']
        
        # Ventes comptant récentes
        entree_ventes_comptant = Vente.objects.filter(
            date_vente__gte=date_debut,
            mode_paiement='comptant'
        ).aggregate(
            total=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), Decimal('0'))
        )['total']
        
        # SORTIES
        sortie_versements = VersementBancaire.objects.filter(
            date_versement_reelle__gte=date_debut
        ).aggregate(
            total=Coalesce(Sum('montant_vente'), Decimal('0'))
        )['total']
        
        sortie_depenses = Depense.objects.filter(
            date_depense__gte=date_debut
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
        
        sortie_paiements_fournisseurs = PaiementFournisseur.objects.filter(
            date_paiement__gte=date_debut
        ).aggregate(
            total=Coalesce(Sum('montant'), Decimal('0'))
        )['total']
        
        # CALCUL FLUX
        total_entrees = entree_recouvrements + entree_ventes_comptant
        total_sorties = sortie_versements + sortie_depenses + sortie_paiements_fournisseurs
        flux_net = total_entrees - total_sorties
        
        # FLUX PAR JOUR (approximatif)
        flux_par_jour = defaultdict(lambda: {'entrees': Decimal('0'), 'sorties': Decimal('0')})
        
        # Recouvrements par jour
        recouvrements_par_jour = Recouvrement.objects.filter(
            date_recouvrement__gte=date_debut
        ).extra(select={'jour': "date(date_recouvrement)"}).values('jour').annotate(
            total=Sum('montant_recouvre')
        )
        
        for item in recouvrements_par_jour:
            jour = item['jour']
            total = item['total'] or Decimal('0')
            flux_par_jour[jour]['entrees'] += total
        
        # Versements par jour
        versements_par_jour = VersementBancaire.objects.filter(
            date_versement_reelle__gte=date_debut
        ).extra(select={'jour': "date(date_versement_reelle)"}).values('jour').annotate(
            total=Sum('montant_vente')
        )
        
        for item in versements_par_jour:
            jour = item['jour']
            total = item['total'] or Decimal('0')
            flux_par_jour[jour]['sorties'] += total
        
        # Convertir en liste triée
        flux_journalier = []
        for jour, data in flux_par_jour.items():
            flux_journalier.append({
                'date': jour,
                'entrees': data['entrees'],
                'sorties': data['sorties'],
                'flux_net': data['entrees'] - data['sorties']
            })
        
        # Trier par date
        flux_journalier.sort(key=lambda x: x['date'])
        
        # Calculer le taux entrées/sorties
        taux_entrees_sorties = 0
        if total_sorties > 0:
            taux_entrees_sorties = (total_entrees / total_sorties * 100)
        
        return {
            'periode': f"{jours} derniers jours",
            'entrees': {
                'recouvrements': entree_recouvrements,
                'ventes_comptant': entree_ventes_comptant,
                'total': total_entrees
            },
            'sorties': {
                'versements': sortie_versements,
                'depenses': sortie_depenses,
                'paiements_fournisseurs': sortie_paiements_fournisseurs,
                'total': total_sorties
            },
            'flux_net': flux_net,
            'flux_journalier': flux_journalier[-10:],  # 10 derniers jours
            'taux_entrees_sorties': taux_entrees_sorties
        }

    # =========================
    # ALERTES ET ACTIONS CRITIQUES (CORRIGÉ)
    # =========================
    @staticmethod
    def get_alertes_critiques():
        """Alertes nécessitant une action immédiate du ROT"""
        alertes = []
        
        # 1. SUPERVISEURS EN DÉFAUT (solde < -50,000)
        superviseurs = Agent.objects.filter(type_agent='entrepot')
        for superviseur in superviseurs:
            solde = RotDashboardService.calculer_solde_superviseur(superviseur)
            if solde < Decimal('-50000'):
                alertes.append({
                    'type': 'superviseur_defaut',
                    'niveau': 'danger',
                    'titre': f"Superviseur en défaut: {superviseur.full_name}",
                    'description': f"Solde: {solde} FCFA",
                    'lien': f"/superviseur/{superviseur.id}/detail",
                    'date': timezone.now()
                })
        
        # 2. FOURNISSEURS AVEC DETTE ÉLEVÉE (> 200,000)
        fournisseurs = Fournisseur.objects.all()
        for fournisseur in fournisseurs:
            dette_restante = fournisseur.dette_restante or Decimal('0')
            if dette_restante > Decimal('200000'):
                alertes.append({
                    'type': 'fournisseur_dette',
                    'niveau': 'warning',
                    'titre': f"Dette élevée: {fournisseur.nom}",
                    'description': f"Dette restante: {dette_restante} FCFA",
                    'lien': f"/fournisseurs/{fournisseur.id}/detail",
                    'date': timezone.now()
                })
        
        # 3. LOT SANS FACTURE
        lots_sans_facture = LotEntrepot.objects.filter(
            factures__isnull=True,
            date_reception__lt=timezone.now() - timedelta(days=7)
        )
        
        for lot in lots_sans_facture:
            alertes.append({
                'type': 'lot_sans_facture',
                'niveau': 'info',
                'titre': f"Lot sans facture: {lot.produit.nom}",
                'description': f"Reçu le {lot.date_reception.strftime('%d/%m/%Y')}",
                'lien': f"/lots/{lot.id}/ajouter-facture",
                'date': timezone.now()
            })
        
        # 4. VERSEMENTS EN RETARD (> 7 jours sans versement)
        for superviseur in superviseurs:
            dernier_versement = VersementBancaire.objects.filter(
                superviseur=superviseur
            ).order_by('-date_versement_reelle').first()
            
            if dernier_versement:
                jours_ecoules = (timezone.now() - dernier_versement.date_versement_reelle).days
                solde = RotDashboardService.calculer_solde_superviseur(superviseur)
                if jours_ecoules > 7 and solde > Decimal('10000'):
                    alertes.append({
                        'type': 'versement_retard',
                        'niveau': 'warning',
                        'titre': f"Versement en retard: {superviseur.full_name}",
                        'description': f"{jours_ecoules} jours sans versement, solde: {solde} FCFA",
                        'lien': f"/versements/nouveau?superviseur={superviseur.id}",
                        'date': timezone.now()
                    })
        
        return alertes

    # =========================
    # TABLEAU DE BORD COMPLET ROT
    # =========================
    @staticmethod
    def build_dashboard_rot(user):
        """Construit le tableau de bord complet pour le ROT"""
        rot = RotDashboardService.get_rot(user)
        if not rot:
            return None

        context = {
            'rot': rot,
            
            # Vue financière globale
            'vue_financiere': RotDashboardService.get_vue_financiere_globale(),
            
            # Gestion fournisseurs
            'situation_fournisseurs': RotDashboardService.get_situation_fournisseurs(),
            
            # Gestion superviseurs
            'situation_superviseurs': RotDashboardService.get_situation_superviseurs(),
            
            # Flux trésorerie
            'flux_tresorerie': RotDashboardService.get_flux_tresorerie_periode(30),
            
            # Alertes critiques
            'alertes': RotDashboardService.get_alertes_critiques(),
            
            # Statistiques rapides
            'stats_rapides': {
                'nombre_lots_actifs': LotEntrepot.objects.filter(quantite_restante__gt=0).count(),
                'nombre_agents_actifs': Agent.objects.filter(type_agent='terrain', est_actif=True).count(),
                'nombre_ventes_mois': Vente.objects.filter(
                    date_vente__gte=timezone.now() - timedelta(days=30)
                ).count(),
                'valeur_stock_total': LotEntrepot.objects.filter(
                    quantite_restante__gt=0
                ).aggregate(
                    total=Coalesce(Sum(F('quantite_restante') * F('prix_achat_unitaire')), Decimal('0'))
                )['total'],
            }
        }

        return context