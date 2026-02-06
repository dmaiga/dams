
# services/fournisseur_service.py
from collections import defaultdict
from decimal import Decimal

from django.db.models import (
    Sum, F, Q, Value, OuterRef, Subquery,Count
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import (
    Fournisseur,
    LotEntrepot,
    Vente,
    Perte,
    PaiementFournisseur,
)

# Constantes
DEC_ZERO = Decimal('0.00')


class FournisseurAnalyseService:
    """
    Service optimisé pour l'analyse fournisseur.
    """

    @staticmethod
    def _normalize_period(date_debut=None, date_fin=None):
        """Retourne des datetime aware pour la période"""
        if date_debut and date_fin:
            # Si déjà datetime naive strings, on suppose format 'YYYY-MM-DD' ou datetime objects
            if isinstance(date_debut, str):
                date_debut = datetime.strptime(date_debut, '%Y-%m-%d')
            if isinstance(date_fin, str):
                date_fin = datetime.strptime(date_fin, '%Y-%m-%d')
        now = timezone.now()
        if not date_debut:
            # début : début de l'année en cours
            date_debut = datetime(now.year, 1, 1)
        if not date_fin:
            # fin : maintenant
            date_fin = now
        # rendre aware si nécessaire
        date_debut = timezone.make_aware(date_debut) if date_debut.tzinfo is None else date_debut
        date_fin = timezone.make_aware(date_fin) if date_fin.tzinfo is None else date_fin
        return date_debut, date_fin


    @staticmethod
    def get_dette_fournisseur(fournisseur_id, date_debut=None, date_fin=None):
        """Récupère la dette actuelle d'un fournisseur"""
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        
        # Calcul de la dette basée sur les ventes
        total = (
            Vente.objects.filter(
                detail_distribution__lot__fournisseur_id=fournisseur_id,
                date_vente__gte=date_debut,
                date_vente__lte=date_fin
            )
            .aggregate(
                total=Coalesce(
                    Sum(
                        F('quantite') *
                        F('detail_distribution__lot__prix_achat_unitaire')
                    ),
                    DEC_ZERO
                )
            )['total']
        )
        
        return total or DEC_ZERO


    @staticmethod
    def get_reste_a_payer_fournisseur(fournisseur_id, date_debut=None, date_fin=None):
        """Calcule le reste à payer pour un fournisseur"""
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        
        # Calculer la dette (coût des ventes)
        dette = FournisseurAnalyseService.get_dette_fournisseur(fournisseur_id, date_debut, date_fin)
        
        # Calculer le total payé
        total_paye = PaiementFournisseur.objects.filter(
            fournisseur_id=fournisseur_id,
            date_paiement__gte=date_debut,
            date_paiement__lte=date_fin
        ).aggregate(
            total=Coalesce(Sum('montant'), DEC_ZERO)
        )['total']
        
        return max(dette - total_paye, DEC_ZERO)


    @staticmethod
    def get_lots_fournisseur(fournisseur_id, date_debut=None, date_fin=None):
        """
        Récupère les lots d'un fournisseur pour une période donnée.
        """
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        
        lots = LotEntrepot.objects.filter(
            fournisseur_id=fournisseur_id,
            date_reception__gte=date_debut,
            date_reception__lte=date_fin
        ).select_related('produit').order_by('-date_reception')
        
        return lots


    @staticmethod
    def get_lots_impayes(fournisseur_id, date_debut=None, date_fin=None):
        """
        Récupère les lots avec dette impayée d'un fournisseur
        """
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        
        # Récupérer tous les lots du fournisseur dans la période
        lots = FournisseurAnalyseService.get_lots_fournisseur(fournisseur_id, date_debut, date_fin)
        
        lots_impayes = []
        for lot in lots:
            # Calculer la dette du lot (coût des ventes)
            ventes_lot = Vente.objects.filter(
                detail_distribution__lot=lot
            ).aggregate(
                total_cout=Coalesce(
                    Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')),
                    DEC_ZERO
                ),
                total_qte=Coalesce(Sum('quantite'), DEC_ZERO)
            )
            
            dette_lot = ventes_lot['total_cout']
            
            # Calculer les paiements pour ce lot
            paiements_lot = PaiementFournisseur.objects.filter(
                lot=lot
            ).aggregate(
                total_paye=Coalesce(Sum('montant'), DEC_ZERO)
            )
            
            total_paye = paiements_lot['total_paye']
            reste_a_payer = max(dette_lot - total_paye, DEC_ZERO)
            
            if reste_a_payer > 0:
                lots_impayes.append({
                    'lot': lot,
                    'dette_lot': dette_lot,
                    'total_paye': total_paye,
                    'reste_a_payer': reste_a_payer,
                    'quantite_vendue': ventes_lot['total_qte']
                })
        
        return lots_impayes


    @staticmethod
    def get_detail_fournisseur(fournisseur_id, date_debut=None, date_fin=None):
        """
        Détail complet pour un fournisseur
        """
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)

        fournisseur = Fournisseur.objects.get(id=fournisseur_id)

        # Lots du fournisseur dans la période
        lots_qs = LotEntrepot.objects.filter(
            fournisseur=fournisseur,
            date_reception__gte=date_debut,
            date_reception__lte=date_fin
        ).select_related('produit')

        lot_ids = list(lots_qs.values_list('id', flat=True))

        # Ventes agrégées par lot (pour éviter N+1)
        ventes_par_lot_qs = (
            Vente.objects.filter(detail_distribution__lot_id__in=lot_ids)
            .values('detail_distribution__lot_id')
            .annotate(
                total_qte=Coalesce(Sum('quantite'), DEC_ZERO),
                total_ca=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), DEC_ZERO),
                total_cout_achat=Coalesce(Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')), DEC_ZERO),
            )
        )
        ventes_par_lot = {v['detail_distribution__lot_id']: v for v in ventes_par_lot_qs}

        # Pertes agrégées par lot
        pertes_par_lot_qs = (
            Perte.objects.filter(lot_id__in=lot_ids)
            .values('lot_id')
            .annotate(total_pertes=Coalesce(Sum('quantite_perdue'), DEC_ZERO)
            )
        )
        pertes_par_lot = {p['lot_id']: p['total_pertes'] for p in pertes_par_lot_qs}
       
        # Paiements agrégés par lot
        paiements_par_lot_qs = (
            PaiementFournisseur.objects.filter(
                lot_id__in=lot_ids,
            )
            .values('lot_id')
            .annotate(total_paye=Coalesce(Sum('montant'), DEC_ZERO))
        )

        paiements_par_lot = {
            p['lot_id']: p['total_paye']
            for p in paiements_par_lot_qs
        }

        # Construire l'analyse par lot
        analyse_lots = []
        for lot in lots_qs:
            v = ventes_par_lot.get(lot.id, {})
            qte_vendue = v.get('total_qte', DEC_ZERO)
            ca_vendue = v.get('total_ca', DEC_ZERO)
            cout_vendue = v.get('total_cout_achat', DEC_ZERO)
            pertes = pertes_par_lot.get(lot.id, DEC_ZERO)

            total_paye_lot = paiements_par_lot.get(lot.id, DEC_ZERO)

            # Dette contractuelle (réception)
            dette_contractuelle = lot.valeur_stock_initiale

            # Dette consommée (bornée par la réception)
            dette_consommee = min(dette_contractuelle, cout_vendue)

            # Reste contractuel à payer (SEULE RÉFÉRENCE POUR LE FOURNISSEUR)
            reste_contractuel = max(dette_contractuelle - total_paye_lot, DEC_ZERO)

            # Survente (erreur opérationnelle)
            survente = max(qte_vendue - lot.quantite_initiale, DEC_ZERO)



            # Déterminer le statut avec couleur
            if lot.quantite_restante == 0:
                statut = "Épuisé"
                statut_classe = "badge badge-success"
                quantite_classe = "text-green-600 font-bold"
            elif lot.quantite_restante < lot.quantite_initiale * Decimal('0.2'):
                statut = "Faible stock"
                statut_classe = "badge badge-warning"
                quantite_classe = "text-orange-600 font-bold"
            else:
                statut = "En stock"
                statut_classe = "badge badge-info"
                quantite_classe = "text-blue-600 font-bold"

            # Calculer le pourcentage d'écoulement
            try:
                if lot.quantite_initiale and lot.quantite_initiale != 0:
                    ecoulement_pct = (qte_vendue / lot.quantite_initiale) * 100
                else:
                    ecoulement_pct = 0
            except Exception:
                ecoulement_pct = 0

            # Calculer le pourcentage de perte
            try:
                if lot.quantite_initiale and lot.quantite_initiale != 0:
                    perte_pct = (pertes / lot.quantite_initiale) * 100
                else:
                    perte_pct = 0
            except Exception:
                perte_pct = 0

            analyse_lots.append({
                'lot': lot,
                'produit': lot.produit,

                # Quantités
                'quantite_recue': lot.quantite_initiale,
                'quantite_restante': lot.quantite_restante,
                'quantite_vendue': qte_vendue,
                'quantite_perdue': pertes,

                # Dettes (BIEN SÉPARÉES)
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
                'reste_contractuel': reste_contractuel,

                # Paiements
                'total_paye_lot': total_paye_lot,

                # Alerte métier
                'survente': survente,

                # Financier
                'prix_achat': lot.prix_achat_unitaire,
                'ca_vendue': ca_vendue,
                'cout_vendue': cout_vendue,

                # Métadonnées
                'date_reception': lot.date_reception,
                'statut': statut,
                'statut_classe': statut_classe,
                'quantite_classe': quantite_classe,
                'ecoulement_pct': round(ecoulement_pct, 2),
                'pourcentage_perte': round(perte_pct, 2),

                # UI
                'pertes_classe': "text-red-600 font-medium" if pertes > 0 else "text-gray-500",
                'survente_classe': "text-red-700 font-bold" if survente > 0 else "text-gray-500",
                'ecoulement_classe': FournisseurAnalyseService._get_ecoulement_classe(ecoulement_pct),
                'pourcentage_perte_classe': FournisseurAnalyseService._get_perte_classe(perte_pct),
            })


        # Analyse par produit (regroupement)
        produit_data = defaultdict(lambda: {
            'produit': None,
            'quantite_vendue': DEC_ZERO,
            'quantite_restante': DEC_ZERO,
            'quantite_perdue': DEC_ZERO,
            'ca_genere': DEC_ZERO,
            'quantite_livree': DEC_ZERO,
            'valeur_livree': DEC_ZERO,
            'lots': [],
            'cout_vendu': DEC_ZERO,
        })

        for lot_info in analyse_lots:
            pr = lot_info['produit']
            pid = pr.id
            produit_data[pid]['produit'] = pr
            produit_data[pid]['quantite_vendue'] += lot_info['quantite_vendue']
            produit_data[pid]['quantite_restante'] += lot_info['quantite_restante']
            produit_data[pid]['quantite_perdue'] += lot_info['quantite_perdue']
            produit_data[pid]['ca_genere'] += lot_info['ca_vendue']
            produit_data[pid]['quantite_livree'] += lot_info['quantite_recue']
            produit_data[pid]['valeur_livree'] += (lot_info['quantite_recue'] * lot_info['prix_achat'])
            produit_data[pid]['lots'].append(lot_info)
            produit_data[pid]['cout_vendu'] += lot_info['cout_vendue']

        produits_analyses = []
        for data in produit_data.values():
            qlv = data['quantite_livree']
            qv = data['quantite_vendue']
            qr = data['quantite_restante']
            qp = data['quantite_perdue']
            ca = data['ca_genere']
            cout_vendu = data['cout_vendu']

            cout_produits_vendus = cout_vendu
            marge_brute = ca - cout_produits_vendus

            # Pourcentage d'écoulement (vendue / livrée)
            pourcentage_ecoulement = (qv / qlv * 100) if qlv and qlv != 0 else 0

            # Taux de marge
            taux_marge = (marge_brute / ca * 100) if ca and ca != 0 else 0

            # Pourcentage de perte
            pourcentage_perte = (qp / qlv * 100) if qlv and qlv != 0 else 0

            # Pourcentage de stock restant
            pourcentage_restant = (qr / qlv * 100) if qlv and qlv != 0 else 0

            # Classes CSS pour les indicateurs couleur
            ecoulement_classe = FournisseurAnalyseService._get_ecoulement_classe(pourcentage_ecoulement)
            marge_classe = FournisseurAnalyseService._get_marge_classe(taux_marge)
            perte_classe = FournisseurAnalyseService._get_perte_classe(pourcentage_perte)
            stock_classe = FournisseurAnalyseService._get_stock_classe(pourcentage_restant)

            produits_analyses.append({
                'produit': data['produit'],
                'quantite_vendue': qv,
                'quantite_restante': qr,
                'quantite_perdue': qp,
                'ca_genere': ca,
                'marge_brute': marge_brute,
                'pourcentage_ecoulement': round(pourcentage_ecoulement, 2),
                'pourcentage_restant': round(pourcentage_restant, 2),
                'pourcentage_perte': round(pourcentage_perte, 2),
                'taux_marge': round(taux_marge, 2),
                'quantite_livree': qlv,
                'nombre_lots': len(data['lots']),
                # Classes pour les indicateurs couleur
                'ecoulement_classe': ecoulement_classe,
                'marge_classe': marge_classe,
                'perte_classe': perte_classe,
                'stock_classe': stock_classe,
                'quantite_restante_classe': "font-bold " + ("text-green-600" if qr == 0 else 
                                                           "text-orange-600" if qr < qlv * Decimal('0.2') else 
                                                           "text-blue-600"),
            })

        # KPI du fournisseur
        dette_contractuelle_totale = sum(
            item['dette_contractuelle'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        dette_consommee_totale = sum(
            item['dette_consommee'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        total_paye_fournisseur = sum(
            item['total_paye_lot'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        reste_contractuel_global = max(
            dette_contractuelle_totale - total_paye_fournisseur,
            DEC_ZERO
        )
       
        # Quantités globales
        total_livre = sum(
            item['quantite_recue'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        total_vendu = sum(
            item['quantite_vendue'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        # Stock restant (quantité)
        stock_restant = sum(
            item['quantite_restante'] for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        # Valeur du stock restant
        valeur_stock_restant = sum(
            item['quantite_restante'] * item['prix_achat']
            for item in analyse_lots
        ) if analyse_lots else DEC_ZERO

        # Taux d’écoulement PONDÉRÉ (le seul correct)
        taux_ecoulement_moyen = round(
            (total_vendu / total_livre * 100)
            if total_livre > 0 else 0,
            2
        )

        kpi_fournisseur = {
            # FINANCE (clair et non discutable)
            'dette_contractuelle': dette_contractuelle_totale,
            'dette_consommee': dette_consommee_totale,
            'total_paye': total_paye_fournisseur,
            'reste_contractuel': reste_contractuel_global,
            'pourcentage_paye': round(
                (total_paye_fournisseur / dette_contractuelle_totale * 100)
                if dette_contractuelle_totale > 0 else 100,
                1
            ),

            # OPÉRATIONNEL
            'stock_restant': stock_restant,
            'valeur_stock_restant': valeur_stock_restant,
            'taux_ecoulement_moyen': taux_ecoulement_moyen,
            'nombre_lots': len(analyse_lots),
        }



        return {
            'fournisseur': fournisseur,
            'analyse_lots': analyse_lots,
            'produits_analyses': sorted(produits_analyses, key=lambda x: x['ca_genere'], reverse=True),
            'kpi_fournisseur': kpi_fournisseur,
            'periode': {'debut': date_debut, 'fin': date_fin, 'type': 'personnalise'}
        }

    @staticmethod
    def _get_ecoulement_classe(pourcentage):
        """Retourne la classe CSS pour le pourcentage d'écoulement"""
        if pourcentage >= 80:
            return "text-green-600 font-bold"
        elif pourcentage >= 50:
            return "text-yellow-600 font-medium"
        elif pourcentage > 0:
            return "text-orange-600 font-medium"
        else:
            return "text-red-600 font-medium"

    @staticmethod
    def _get_marge_classe(taux):
        """Retourne la classe CSS pour le taux de marge"""
        if taux >= 30:
            return "text-green-600 font-bold"
        elif taux >= 15:
            return "text-yellow-600 font-medium"
        elif taux > 0:
            return "text-orange-600 font-medium"
        else:
            return "text-red-600 font-medium"

    @staticmethod
    def _get_perte_classe(pourcentage):
        """Retourne la classe CSS pour le pourcentage de perte"""
        if pourcentage == 0:
            return "text-green-600 font-medium"
        elif pourcentage <= 5:
            return "text-yellow-600 font-medium"
        elif pourcentage <= 10:
            return "text-orange-600 font-medium"
        else:
            return "text-red-600 font-bold"

    @staticmethod
    def _get_stock_classe(pourcentage):
        """Retourne la classe CSS pour le pourcentage de stock restant"""
        if pourcentage == 0:
            return "text-green-600 font-bold"  # Tout écoulé = bon
        elif pourcentage <= 30:
            return "text-blue-600 font-medium"  # Faible stock = normal
        elif pourcentage <= 50:
            return "text-yellow-600 font-medium"  # Stock moyen = attention
        else:
            return "text-orange-600 font-bold"  # Gros stock = problème d'écoulement



    from datetime import datetime, timedelta
    from django.db.models import Sum, F, Count
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    DEC_ZERO = 0

    # =====================================================
    # ANALYSE GLOBALE (SANS FILTRE TEMPOREL)
    # =====================================================
    @staticmethod
    def get_analyse_globale():
        """
        Analyse globale sans filtre temporel
        Vision état (direction)
        """
        return FournisseurAnalyseService.get_analyse_periode(None, None)

    # =====================================================
    # ANALYSE ANNUELLE
    # =====================================================
    @staticmethod
    def get_analyse_annuelle(annee=None):
        if annee is None:
            annee = timezone.now().year
        date_debut = datetime(annee, 1, 1)
        date_fin = datetime(annee, 12, 31, 23, 59, 59)
        return FournisseurAnalyseService.get_analyse_periode(date_debut, date_fin)

    # =====================================================
    # ANALYSE MENSUELLE
    # =====================================================
    @staticmethod
    def get_analyse_mensuelle(mois=None, annee=None):
        now = timezone.now()
        mois = mois or now.month
        annee = annee or now.year

        date_debut = datetime(annee, mois, 1)
        if mois == 12:
            date_fin = datetime(annee + 1, 1, 1) - timedelta(seconds=1)
        else:
            date_fin = datetime(annee, mois + 1, 1) - timedelta(seconds=1)

        return FournisseurAnalyseService.get_analyse_periode(date_debut, date_fin)

    
    # =====================================================
    # ANALYSE CORE (CORRIGÉE)
    # =====================================================
    @staticmethod
    def get_analyse_periode(date_debut=None, date_fin=None):
        """
        LOGIQUE CORRIGÉE :
        - Dette contractuelle = réceptions (lots)
        - Dette consommée = ventes liées aux lots
        - Paiements = UNIQUEMENT paiements rattachés aux lots
        => cohérence parfaite avec le détail fournisseur
        """
    
        # =========================
        # LOTS → DETTE CONTRACTUELLE
        # =========================
        lots_qs = LotEntrepot.objects.filter(fournisseur__isnull=False)
    
        if date_debut:
            lots_qs = lots_qs.filter(date_reception__gte=date_debut)
        if date_fin:
            lots_qs = lots_qs.filter(date_reception__lte=date_fin)
    
        lots_agg = (
            lots_qs
            .values('fournisseur')
            .annotate(
                dette_contractuelle=Coalesce(
                    Sum(F('quantite_initiale') * F('prix_achat_unitaire')),
                    DEC_ZERO
                ),
                quantite_livree=Coalesce(Sum('quantite_initiale'), DEC_ZERO),
                stock_restant=Coalesce(Sum('quantite_restante'), DEC_ZERO),
                valeur_stock_restant=Coalesce(
                    Sum(F('quantite_restante') * F('prix_achat_unitaire')),
                    DEC_ZERO
                ),
                nombre_lots=Count('id')
            )
        )
        lots_by_fournisseur = {l['fournisseur']: l for l in lots_agg}
    
        # =========================
        # VENTES → DETTE CONSOMMÉE
        # =========================
        ventes_qs = Vente.objects.filter(
            detail_distribution__lot__fournisseur__isnull=False
        )
    
        if date_debut:
            ventes_qs = ventes_qs.filter(
                detail_distribution__lot__date_reception__gte=date_debut
            )
        if date_fin:
            ventes_qs = ventes_qs.filter(
                detail_distribution__lot__date_reception__lte=date_fin
            )
    
        ventes_agg = (
            ventes_qs
            .values('detail_distribution__lot__fournisseur')
            .annotate(
                quantite_vendue=Coalesce(Sum('quantite'), DEC_ZERO),
                dette_consommee=Coalesce(
                    Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')),
                    DEC_ZERO
                ),
                chiffre_affaires=Coalesce(
                    Sum(F('quantite') * F('prix_vente_unitaire')),
                    DEC_ZERO
                )
            )
        )
        ventes_by_fournisseur = {
            v['detail_distribution__lot__fournisseur']: v for v in ventes_agg
        }
    
        # =========================
        # PAIEMENTS → PAR LOT (CORRIGÉ)
        # =========================
        paiements_lots_agg = (
            PaiementFournisseur.objects
            .filter(
                lot__fournisseur__isnull=False,
                est_supprime=False
            )
            .values('lot__fournisseur')
            .annotate(
                total_paye=Coalesce(Sum('montant'), DEC_ZERO)
            )
        )
    
        paiements_by_fournisseur = {
            p['lot__fournisseur']: p['total_paye']
            for p in paiements_lots_agg
        }
    
        # =========================
        # CONSTRUCTION ANALYSE
        # =========================
        fournisseur_ids = (
            set(lots_by_fournisseur) |
            set(ventes_by_fournisseur) |
            set(paiements_by_fournisseur)
        )
    
        fournisseurs = Fournisseur.objects.filter(
            id__in=fournisseur_ids
        ).order_by('nom')
    
        analyse_data = []
    
        for f in fournisseurs:
            fid = f.id
    
            lot = lots_by_fournisseur.get(fid, {})
            vente = ventes_by_fournisseur.get(fid, {})
            total_paye = paiements_by_fournisseur.get(fid, DEC_ZERO)
    
            dette_contractuelle = lot.get('dette_contractuelle', DEC_ZERO)
            dette_consommee = min(
                vente.get('dette_consommee', DEC_ZERO),
                dette_contractuelle
            )
    
            reste_contractuel = max(dette_contractuelle - total_paye, DEC_ZERO)
    
            quantite_livree = lot.get('quantite_livree', DEC_ZERO)
            quantite_vendue = vente.get('quantite_vendue', DEC_ZERO)
    
            ecoulement_pct = (
                (quantite_vendue / quantite_livree) * 100
                if quantite_livree > 0 else 0
            )
    
            marge_brute = (
                vente.get('chiffre_affaires', DEC_ZERO)
                - vente.get('dette_consommee', DEC_ZERO)
            )
    
            analyse_data.append({
                'fournisseur': f,
    
                # Quantités
                'quantite_livree': quantite_livree,
                'quantite_vendue': quantite_vendue,
                'stock_restant': lot.get('stock_restant', DEC_ZERO),
                'valeur_stock_restant': lot.get('valeur_stock_restant', DEC_ZERO),
    
                # Montants
                'montant_livre': dette_contractuelle,
                'montant_ecoule': vente.get('chiffre_affaires', DEC_ZERO),
    
                # Dettes (ALIGNÉES DÉTAIL)
                'dette_contractuelle': dette_contractuelle,
                'dette_consommee': dette_consommee,
                'total_paye': total_paye,
                'reste_contractuel': reste_contractuel,
    
                # Analyse
                'ecoulement_pct': round(ecoulement_pct, 2),
                'marge_brute': marge_brute,
                'nombre_lots': lot.get('nombre_lots', 0),
            })
    
        # =========================
        # KPI GLOBAUX
        # =========================
        dette_contractuelle_globale = sum(i['dette_contractuelle'] for i in analyse_data)
        dette_consommee_globale = sum(i['dette_consommee'] for i in analyse_data)
        total_paye_global = sum(i['total_paye'] for i in analyse_data)
    
        kpi_globaux = {
            'dette_contractuelle_globale': dette_contractuelle_globale,
            'dette_consommee_globale': dette_consommee_globale,
            'total_paye': total_paye_global,
            'reste_contractuel_global': max(
                dette_contractuelle_globale - total_paye_global,
                DEC_ZERO
            ),
            'pourcentage_paye_global': round(
                (total_paye_global / dette_contractuelle_globale * 100)
                if dette_contractuelle_globale > 0 else 100,
                1
            ),
            'marge_brute_totale': sum(i['marge_brute'] for i in analyse_data),
        }
    
        return {
            'analyse_data': analyse_data,
            'kpi_globaux': kpi_globaux,
            'periode': {
                'type': 'globale' if not date_debut and not date_fin else 'periode',
                'debut': date_debut,
                'fin': date_fin,
            }
        }
    