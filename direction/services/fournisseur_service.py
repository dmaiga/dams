# services/fournisseur_service.py
from collections import defaultdict
from decimal import Decimal

from django.db.models import (
    Sum, F, Q, Value, OuterRef, Subquery,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import (
    Fournisseur,
    LotEntrepot,
    Vente,
    Perte,
)

# Constantes
DEC_ZERO = Decimal('0.00')


class FournisseurAnalyseService:
    """
    Service optimisé pour l'analyse fournisseur.

    Principes :
    - DETTE = somme(quantité vendue * prix_achat_unitaire) pour les ventes liées aux lots du fournisseur
      (=> conforme à ta logique métier).
    - Toutes les agrégations lourdes se font par requêtes groupées SQL (values().annotate()).
    - Minimisation des objets en mémoire : on récupère uniquement ce qui est nécessaire.
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
    def get_analyse_annuelle(annee=None):
        """Analyse annuelle (optimisée)"""
        if annee is None:
            annee = timezone.now().year
        date_debut = datetime(annee, 1, 1)
        date_fin = datetime(annee, 12, 31, 23, 59, 59)
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        return FournisseurAnalyseService.get_analyse_periode(date_debut, date_fin)

    @staticmethod
    def get_analyse_mensuelle(mois=None, annee=None):
        """Analyse mensuelle (optimisée)"""
        now = timezone.now()
        if mois is None:
            mois = now.month
        if annee is None:
            annee = now.year
        date_debut = datetime(annee, mois, 1)
        if mois == 12:
            date_fin = datetime(annee + 1, 1, 1) - timedelta(seconds=1)
        else:
            date_fin = datetime(annee, mois + 1, 1) - timedelta(seconds=1)
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)
        return FournisseurAnalyseService.get_analyse_periode(date_debut, date_fin)

    @staticmethod
    def get_analyse_periode(date_debut=None, date_fin=None):
        """
        Analyse par fournisseur pour une période donnée.
        Retour :
        {
            'analyse_data': [ {fournisseur, quantite_livree, montant_livre, quantite_ecoulee,
                               montant_ecoule, dette_actuelle, ...}, ... ],
            'kpi_globaux': {...},
            'periode': {...}
        }
        """
        date_debut, date_fin = FournisseurAnalyseService._normalize_period(date_debut, date_fin)

        # 1) Agrégats sur les lots par fournisseur : quantite_livree, valeur_livree, quantite_restante, valeur_stock_restant, nombre_lots
        lots_agg = (
            LotEntrepot.objects.filter(date_reception__gte=date_debut, date_reception__lte=date_fin)
            .values('fournisseur')
            .annotate(
                quantite_livree=Coalesce(Sum('quantite_initiale'), DEC_ZERO),
                valeur_livree=Coalesce(Sum(F('quantite_initiale') * F('prix_achat_unitaire')), DEC_ZERO),
                stock_restant=Coalesce(Sum('quantite_restante'), DEC_ZERO),
                valeur_stock_restant=Coalesce(Sum(F('quantite_restante') * F('prix_achat_unitaire')), DEC_ZERO),
                nombre_lots=Coalesce(Sum(Value(1)), 0)  # simple count approximation
            )
        )

        lots_by_fournisseur = {item['fournisseur']: item for item in lots_agg}

        # 2) Agrégats sur les ventes (CA et coût achat) groupés par fournisseur (via lot -> fournisseur)
        ventes_agg = (
            Vente.objects.filter(
                detail_distribution__lot__date_reception__gte=date_debut,
                detail_distribution__lot__date_reception__lte=date_fin,
                detail_distribution__lot__fournisseur__isnull=False
            )
            .values('detail_distribution__lot__fournisseur')
            .annotate(
                fournisseur_id=F('detail_distribution__lot__fournisseur'),
                total_qte_vendue=Coalesce(Sum('quantite'), DEC_ZERO),
                total_ca=Coalesce(Sum(F('quantite') * F('prix_vente_unitaire')), DEC_ZERO),
                total_cout_achat=Coalesce(Sum(F('quantite') * F('detail_distribution__lot__prix_achat_unitaire')), DEC_ZERO),
            )
        )

        ventes_by_fournisseur = {item['fournisseur_id']: item for item in ventes_agg}

        # 3) Agrégats pertes groupés par fournisseur (via lot -> fournisseur)
        pertes_agg = (
            Perte.objects.filter(
                lot__date_reception__gte=date_debut,
                lot__date_reception__lte=date_fin,
                lot__fournisseur__isnull=False
            )
            .values('lot__fournisseur')
            .annotate(
                fournisseur_id=F('lot__fournisseur'),
                total_pertes=Coalesce(Sum('quantite_perdue'), DEC_ZERO)
            )
        )
        pertes_by_fournisseur = {item['fournisseur_id']: item for item in pertes_agg}

        # 4) Récupérer la liste des fournisseurs concernés (ceux qui ont lots dans période OU ventes)
        fournisseur_ids = set()
        fournisseur_ids.update([k for k in lots_by_fournisseur.keys() if k is not None])
        fournisseur_ids.update([k for k in ventes_by_fournisseur.keys() if k is not None])
        fournisseur_ids.update([k for k in pertes_by_fournisseur.keys() if k is not None])

        fournisseurs = Fournisseur.objects.filter(id__in=list(fournisseur_ids)).order_by('nom')

        analyse_data = []

        for f in fournisseurs:
            lid = f.id
            lots_info = lots_by_fournisseur.get(lid, {})
            ventes_info = ventes_by_fournisseur.get(lid, {})
            pertes_info = pertes_by_fournisseur.get(lid, {})

            quantite_livree = lots_info.get('quantite_livree', DEC_ZERO)
            montant_livre = lots_info.get('valeur_livree', DEC_ZERO)
            stock_restant = lots_info.get('stock_restant', DEC_ZERO)
            valeur_stock_restant = lots_info.get('valeur_stock_restant', DEC_ZERO)
            nombre_lots = lots_info.get('nombre_lots', 0)

            quantite_ecoulee = ventes_info.get('total_qte_vendue', DEC_ZERO)
            montant_ecoule = ventes_info.get('total_ca', DEC_ZERO)
            cout_achat_des_vendus = ventes_info.get('total_cout_achat', DEC_ZERO)

            # Dette = coût d'achat des quantités vendues (conforme à ta logique métier)
            dette_actuelle = cout_achat_des_vendus

            quantite_perdue = pertes_info.get('total_pertes', DEC_ZERO)

            pourcentage_ecoulement = 0
            if quantite_livree and quantite_livree != 0:
                try:
                    pourcentage_ecoulement = (quantite_ecoulee / quantite_livree) * 100
                except Exception:
                    pourcentage_ecoulement = 0

            # Marge brute réelle = CA - cout_achat_des_vendus
            marge_brute = montant_ecoule - cout_achat_des_vendus

            taux_pertes = round(((quantite_perdue / quantite_livree) * 100) if quantite_livree and quantite_livree != 0 else 0, 2)

            analyse_data.append({
                'fournisseur': f,
                'quantite_livree': quantite_livree,
                'montant_livre': montant_livre,
                'quantite_ecoulee': quantite_ecoulee,
                'montant_ecoule': montant_ecoule,
                'cout_achat_des_vendus': cout_achat_des_vendus,
                'dette_actuelle': dette_actuelle,
                'pourcentage_ecoulement': round(pourcentage_ecoulement, 2),
                'quantite_perdue': quantite_perdue,
                'taux_pertes': taux_pertes,
                'stock_restant': stock_restant,
                'valeur_stock_restant': valeur_stock_restant,
                'marge_brute': marge_brute,
                'nombre_lots': nombre_lots,
            })

        # KPI globaux (agrégats simples)
        if analyse_data:
            dette_totale = sum(item['dette_actuelle'] for item in analyse_data)
            marge_brute_totale = sum(item['marge_brute'] for item in analyse_data)
            stock_total_restant = sum(item['stock_restant'] for item in analyse_data)
            valeur_stock_total = sum(item['valeur_stock_restant'] for item in analyse_data)
            taux_perte_moyen = round(sum(item['taux_pertes'] for item in analyse_data) / len(analyse_data), 2)
            ecoulement_moyen = round(sum(item['pourcentage_ecoulement'] for item in analyse_data) / len(analyse_data), 2)
        else:
            dette_totale = DEC_ZERO
            marge_brute_totale = DEC_ZERO
            stock_total_restant = DEC_ZERO
            valeur_stock_total = DEC_ZERO
            taux_perte_moyen = 0
            ecoulement_moyen = 0

        kpi_globaux = {
            'dette_totale': dette_totale,
            'marge_brute_totale': marge_brute_totale,
            'stock_total_restant': stock_total_restant,
            'valeur_stock_total': valeur_stock_total,
            'taux_perte_moyen': taux_perte_moyen,
            'ecoulement_moyen': ecoulement_moyen,
        }

        return {
            'analyse_data': sorted(analyse_data, key=lambda x: x['dette_actuelle'], reverse=True),
            'kpi_globaux': kpi_globaux,
            'periode': {'debut': date_debut, 'fin': date_fin, 'type': 'personnalise'}
        }


    @staticmethod
    def get_detail_fournisseur(fournisseur_id, date_debut=None, date_fin=None):
        """
        Détail complet pour un fournisseur avec :
        - Quantité de pertes dans les lots
        - Quantité restante dans l'analyse commerciale
        - Indicateurs couleur pour la quantité restante
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
            .annotate(total_pertes=Coalesce(Sum('quantite_perdue'), DEC_ZERO))
        )
        pertes_par_lot = {p['lot_id']: p['total_pertes'] for p in pertes_par_lot_qs}

        # Construire l'analyse par lot
        analyse_lots = []
        for lot in lots_qs:
            v = ventes_par_lot.get(lot.id, {})
            qte_vendue = v.get('total_qte', DEC_ZERO)
            ca_vendue = v.get('total_ca', DEC_ZERO)
            cout_vendue = v.get('total_cout_achat', DEC_ZERO)
            pertes = pertes_par_lot.get(lot.id, DEC_ZERO)

            dette_lot = cout_vendue  # dette basée sur ventes réalisées

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
                'quantite_recue': lot.quantite_initiale,
                'quantite_restante': lot.quantite_restante,
                'quantite_vendue': qte_vendue,
                'quantite_perdue': pertes,
                'pourcentage_perte': round(perte_pct, 2),
                'prix_achat': lot.prix_achat_unitaire,
                'dette_lot': dette_lot,
                'ca_vendue': ca_vendue,
                'cout_vendue': cout_vendue,
                'date_reception': lot.date_reception,
                'statut': statut,
                'statut_classe': statut_classe,
                'quantite_classe': quantite_classe,
                'pertes': pertes,
                'ecoulement_pct': round(ecoulement_pct, 2),
                # Nouveau: classes pour les indicateurs couleur
                'pertes_classe': "text-red-600 font-medium" if pertes > 0 else "text-gray-500",
                'ecoulement_classe': FournisseurAnalyseService._get_ecoulement_classe(ecoulement_pct),
                'pourcentage_perte_classe': FournisseurAnalyseService._get_perte_classe(perte_pct),
            })

        # Analyse par produit (regroupement) - AJOUT DE LA QUANTITÉ RESTANTE
        produit_data = defaultdict(lambda: {
            'produit': None,
            'quantite_vendue': DEC_ZERO,
            'quantite_restante': DEC_ZERO,  # NOUVEAU
            'quantite_perdue': DEC_ZERO,    # NOUVEAU
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
            produit_data[pid]['quantite_restante'] += lot_info['quantite_restante']  # NOUVEAU
            produit_data[pid]['quantite_perdue'] += lot_info['quantite_perdue']      # NOUVEAU
            produit_data[pid]['ca_genere'] += lot_info['ca_vendue']
            produit_data[pid]['quantite_livree'] += lot_info['quantite_recue']
            produit_data[pid]['valeur_livree'] += (lot_info['quantite_recue'] * lot_info['prix_achat'])
            produit_data[pid]['lots'].append(lot_info)
            produit_data[pid]['cout_vendu'] += lot_info['cout_vendue']

        produits_analyses = []
        for data in produit_data.values():
            qlv = data['quantite_livree']
            qv = data['quantite_vendue']
            qr = data['quantite_restante']  # NOUVEAU
            qp = data['quantite_perdue']    # NOUVEAU
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
                'quantite_restante': qr,          # NOUVEAU
                'quantite_perdue': qp,            # NOUVEAU
                'ca_genere': ca,
                'marge_brute': marge_brute,
                'pourcentage_ecoulement': round(pourcentage_ecoulement, 2),
                'pourcentage_restant': round(pourcentage_restant, 2),  # NOUVEAU
                'pourcentage_perte': round(pourcentage_perte, 2),      # NOUVEAU
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
        dette_totale = sum(item['dette_lot'] for item in analyse_lots) if analyse_lots else DEC_ZERO
        stock_restant = sum(item['quantite_restante'] for item in analyse_lots) if analyse_lots else DEC_ZERO
        valeur_stock_restant = sum(item['quantite_restante'] * item['prix_achat'] for item in analyse_lots) if analyse_lots else DEC_ZERO
        total_perdu = sum(item['quantite_perdue'] for item in analyse_lots) if analyse_lots else DEC_ZERO

        taux_perte_moyen = round(
            sum((item['pourcentage_perte']) for item in analyse_lots if item['quantite_recue'] and item['quantite_recue'] != 0) / len(analyse_lots)
            if analyse_lots else 0, 2
        )

        taux_ecoulement_moyen = round(
            sum(item['ecoulement_pct'] for item in analyse_lots) / len(analyse_lots)
            if analyse_lots else 0, 2
        )

        kpi_fournisseur = {
            'dette_totale': dette_totale,
            'stock_restant': stock_restant,
            'valeur_stock_restant': valeur_stock_restant,
            'total_perdu': total_perdu,
            'taux_perte_moyen': taux_perte_moyen,
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