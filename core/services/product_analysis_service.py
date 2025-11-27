from django.db.models import Sum, Avg, Count, Q, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Produit, LotEntrepot, Vente, Fournisseur, Perte, DetailDistribution

class ProductAnalysisService:
    
    @staticmethod
    def get_product_kpis():
        """Calcule les KPI globaux pour tous les produits"""
        # Stock total (unités)
        total_stock = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).aggregate(
            total=Sum('quantite_restante')
        )['total'] or Decimal('0')
        
        # Valeur stock disponible (valeur actuelle du stock)
        lots_avec_valeur = LotEntrepot.objects.filter(
            quantite_restante__gt=0
        ).annotate(
            valeur_stock_disponible=ExpressionWrapper(
                F('quantite_restante') * F('prix_achat_unitaire'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        total_valeur_stock_disponible = sum(lot.valeur_stock_disponible for lot in lots_avec_valeur)
        
        # Valeur d'achat total des produits (investissement total initial)
        valeur_achat_total = LotEntrepot.objects.aggregate(
            total=Sum(F('quantite_initiale') * F('prix_achat_unitaire'))
        )['total'] or Decimal('0')
        
        # Chiffre d'affaires total (toutes les ventes)
        ventes_ca = Vente.objects.annotate(
            montant_vente=ExpressionWrapper(
                F('quantite') * F('prix_vente_unitaire'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
        ca_total = sum(vente.montant_vente for vente in ventes_ca)
        
        # Valeur des pertes (quantités perdues * prix d'achat)
        pertes_valeur = Decimal('0')
        for perte in Perte.objects.all():
            prix_achat = perte.lot.prix_achat_unitaire or Decimal('0')
            pertes_valeur += perte.quantite_perdue * prix_achat
        
        # Marge totale générée (uniquement sur les produits vendus)
        marge_totale = Decimal('0')
        for vente in Vente.objects.all():
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            marge_totale += marge_vente
        
        return {
            'total_stock': total_stock,
            'total_valeur_stock_disponible': total_valeur_stock_disponible,
            'valeur_achat_total': valeur_achat_total,
            'ca_total': ca_total,
            'pertes_valeur': pertes_valeur,
            'marge_totale': marge_totale,
        }
    
    @staticmethod
    def get_products_by_supplier(supplier_id=None):
        """Retourne les produits avec leurs informations par fournisseur"""
        # Si un fournisseur est spécifié, on groupe par produit ET fournisseur
        if supplier_id:
            # Récupérer tous les lots du fournisseur
            lots_fournisseur = LotEntrepot.objects.filter(
                fournisseur_id=supplier_id
            ).select_related('produit', 'fournisseur').prefetch_related('pertes')
            
            # Grouper par produit
            produits_par_fournisseur = {}
            for lot in lots_fournisseur:
                produit = lot.produit
                if produit.id not in produits_par_fournisseur:
                    produits_par_fournisseur[produit.id] = {
                        'product': produit,
                        'lots': [],
                        'fournisseur_specifique': lot.fournisseur,
                        'total_stock': Decimal('0'),
                        'total_valeur_stock_disponible': Decimal('0'),
                        'total_initial_quantity': Decimal('0'),
                        'total_losses_quantite': Decimal('0'),
                        'total_losses_valeur': Decimal('0'),
                    }
                
                produits_par_fournisseur[produit.id]['lots'].append(lot)
                produits_par_fournisseur[produit.id]['total_stock'] += lot.quantite_restante
                produits_par_fournisseur[produit.id]['total_valeur_stock_disponible'] += (
                    lot.quantite_restante * (lot.prix_achat_unitaire or Decimal('0'))
                )
                produits_par_fournisseur[produit.id]['total_initial_quantity'] += lot.quantite_initiale
                
                # Calcul des pertes en quantité et valeur
                pertes_quantite = sum(perte.quantite_perdue for perte in lot.pertes.all())
                pertes_valeur = pertes_quantite * (lot.prix_achat_unitaire or Decimal('0'))
                produits_par_fournisseur[produit.id]['total_losses_quantite'] += pertes_quantite
                produits_par_fournisseur[produit.id]['total_losses_valeur'] += pertes_valeur
            
            products_data = list(produits_par_fournisseur.values())
            
        else:
            # Tous les produits, tous fournisseurs confondus
            queryset = Produit.objects.prefetch_related(
                'lots',
                'lots__fournisseur',
                'lots__pertes'
            )
            products_data = []
            
            for product in queryset.distinct():
                lots = product.lots.all()
                
                total_stock = sum(lot.quantite_restante for lot in lots)
                total_valeur_stock_disponible = sum(
                    lot.quantite_restante * (lot.prix_achat_unitaire or Decimal('0')) 
                    for lot in lots
                )
                total_initial_quantity = sum(lot.quantite_initiale for lot in lots)
                
                # Calcul des pertes
                total_losses_quantite = Decimal('0')
                total_losses_valeur = Decimal('0')
                for lot in lots:
                    pertes_quantite = sum(perte.quantite_perdue for perte in lot.pertes.all())
                    total_losses_quantite += pertes_quantite
                    total_losses_valeur += pertes_quantite * (lot.prix_achat_unitaire or Decimal('0'))
                
                # Fournisseurs distincts
                suppliers = list(set(lot.fournisseur for lot in lots if lot.fournisseur))
                
                products_data.append({
                    'product': product,
                    'lots': lots,
                    'fournisseur_specifique': None,
                    'total_stock': total_stock,
                    'total_valeur_stock_disponible': total_valeur_stock_disponible,
                    'total_initial_quantity': total_initial_quantity,
                    'total_losses_quantite': total_losses_quantite,
                    'total_losses_valeur': total_losses_valeur,
                    'suppliers': suppliers,
                    'supplier_count': len(suppliers),
                })
        
        # Calculer les métriques de performance pour chaque produit
        for product_data in products_data:
            product = product_data['product']
            
            # Ventes (toutes périodes)
            ventes = Vente.objects.filter(
                detail_distribution__lot__produit=product
            )
            
            if supplier_id and product_data['fournisseur_specifique']:
                # Filtrer les ventes par lots du fournisseur spécifique
                lots_ids = [lot.id for lot in product_data['lots']]
                ventes = ventes.filter(
                    detail_distribution__lot_id__in=lots_ids
                )
            
            total_sales_quantity = sum(vente.quantite for vente in ventes)
            total_sales_revenue = sum(
                vente.quantite * (vente.prix_vente_unitaire or Decimal('0')) 
                for vente in ventes
            )
            
            # Calcul de la marge pour ce produit/fournisseur
            marge_totale = Decimal('0')
            for vente in ventes:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_totale += marge_vente
            
            # Taux de marge en pourcentage
            taux_marge = Decimal('0')
            if total_sales_revenue > 0:
                taux_marge = (marge_totale / total_sales_revenue) * Decimal('100')
            
            # Déterminer le statut du stock avec des seuils fixes
            stock_status = 'NORMAL'
            total_stock = product_data['total_stock']
            if total_stock <= 0:
                stock_status = 'RUPTURE'
            elif total_stock < 30:  # Seuil critique fixe
                stock_status = 'CRITIQUE'
            elif total_stock > 200:  # Seuil excédentaire fixe
                stock_status = 'EXCÉDENTAIRE'
            
            product_data.update({
                'total_sales_quantity': total_sales_quantity,
                'total_sales_revenue': total_sales_revenue,
                'marge_totale': marge_totale,
                'taux_marge': float(taux_marge),
                'stock_status': stock_status,
            })
        
        return products_data
    
    @staticmethod
    def get_ventes_par_agent(supplier_id=None):
        """Retourne les ventes réalisées par agent pour un fournisseur spécifique"""
        # Base queryset des ventes (toutes périodes)
        ventes = Vente.objects.select_related(
            'agent',
            'detail_distribution__lot__produit',
            'detail_distribution__lot__fournisseur'
        )
        
        # Filtrer par fournisseur si spécifié
        if supplier_id:
            ventes = ventes.filter(
                detail_distribution__lot__fournisseur_id=supplier_id
            )
        
        # Grouper par agent
        ventes_par_agent = {}
        for vente in ventes:
            agent = vente.agent
            if agent.id not in ventes_par_agent:
                ventes_par_agent[agent.id] = {
                    'agent': agent,
                    'ventes': [],
                    'total_quantite': Decimal('0'),
                    'total_ca': Decimal('0'),
                    'total_marge': Decimal('0'),
                    'produits_vendus': set()
                }
            
            # Calcul de la marge pour cette vente
            prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
            marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
            
            ventes_par_agent[agent.id]['ventes'].append(vente)
            ventes_par_agent[agent.id]['total_quantite'] += vente.quantite
            ventes_par_agent[agent.id]['total_ca'] += vente.quantite * vente.prix_vente_unitaire
            ventes_par_agent[agent.id]['total_marge'] += marge_vente
            ventes_par_agent[agent.id]['produits_vendus'].add(vente.detail_distribution.lot.produit.nom)
        
        # Convertir en liste et calculer les taux
        result = []
        for agent_data in ventes_par_agent.values():
            taux_marge = Decimal('0')
            if agent_data['total_ca'] > 0:
                taux_marge = (agent_data['total_marge'] / agent_data['total_ca']) * Decimal('100')
            
            result.append({
                'agent': agent_data['agent'],
                'total_quantite': agent_data['total_quantite'],
                'total_ca': agent_data['total_ca'],
                'total_marge': agent_data['total_marge'],
                'taux_marge': float(taux_marge),
                'nombre_produits': len(agent_data['produits_vendus']),
                'produits_vendus': list(agent_data['produits_vendus'])[:3]  # 3 premiers produits
            })
        
        # Trier par CA décroissant
        return sorted(result, key=lambda x: x['total_ca'], reverse=True)
    
    @staticmethod
    def get_product_detail(product_id, supplier_id=None):
        """Retourne les détails complets d'un produit avec focus sur les lots"""
        try:
            product = Produit.objects.prefetch_related(
                'lots',
                'lots__fournisseur',
                'lots__pertes'
            ).get(id=product_id)
            
            # Filtrer les lots par fournisseur si spécifié
            lots = product.lots.all()
            if supplier_id:
                lots = lots.filter(fournisseur_id=supplier_id)
                fournisseur_specifique = Fournisseur.objects.get(id=supplier_id)
            else:
                fournisseur_specifique = None
            
            # Statistiques des ventes (toutes périodes)
            ventes = Vente.objects.filter(
                detail_distribution__lot__produit=product
            )
            if supplier_id:
                lots_ids = [lot.id for lot in lots]
                ventes = ventes.filter(detail_distribution__lot_id__in=lots_ids)
            
            # Calcul de la marge totale
            marge_totale = Decimal('0')
            for vente in ventes:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_totale += marge_vente
            
            # Calcul des pertes totales pour ce produit
            pertes_quantite_totale = Decimal('0')
            pertes_valeur_totale = Decimal('0')
            for lot in lots:
                pertes_quantite = sum(perte.quantite_perdue for perte in lot.pertes.all())
                pertes_quantite_totale += pertes_quantite
                pertes_valeur_totale += pertes_quantite * (lot.prix_achat_unitaire or Decimal('0'))
            
            sales_stats = {
                'total_quantity': sum(vente.quantite for vente in ventes),
                'total_revenue': sum(
                    vente.quantite * (vente.prix_vente_unitaire or Decimal('0')) 
                    for vente in ventes
                ),
                'total_marge': marge_totale,
                'pertes_quantite': pertes_quantite_totale,
                'pertes_valeur': pertes_valeur_totale,
                'sales_count': ventes.count()
            }
            
            # Taux de marge
            taux_marge = Decimal('0')
            if sales_stats['total_revenue'] > 0:
                taux_marge = (marge_totale / sales_stats['total_revenue']) * Decimal('100')
            sales_stats['taux_marge'] = float(taux_marge)
            
            # Calculer la marge pour chaque lot - TRI PAR DATE DE RÉCEPTION DÉCROISSANTE
            lots_avec_marge = []
            for lot in lots.order_by('-date_reception'):  # Tri ajouté ici
                # Ventes pour ce lot spécifique
                ventes_lot = ventes.filter(detail_distribution__lot=lot)
                marge_lot = Decimal('0')
                for vente in ventes_lot:
                    marge_vente = (vente.prix_vente_unitaire - lot.prix_achat_unitaire) * vente.quantite
                    marge_lot += marge_vente
                
                lots_avec_marge.append({
                    'lot': lot,
                    'marge': marge_lot
                })
            
            # Ventes par mois (12 derniers mois) avec marge - TRI DÉCROISSANT POUR MOIS ACTUEL EN PREMIER
            monthly_sales = []
            today = timezone.now()
            
            for i in range(12):
                month_date = today - timedelta(days=30*i)
                debut_mois = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                fin_mois = (debut_mois + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                ventes_mois = ventes.filter(date_vente__range=[debut_mois, fin_mois])
                quantite_mois = sum(vente.quantite for vente in ventes_mois)
                revenue_mois = sum(
                    vente.quantite * (vente.prix_vente_unitaire or Decimal('0')) 
                    for vente in ventes_mois
                )
                
                # Calcul de la marge pour ce mois
                marge_mois = Decimal('0')
                for vente in ventes_mois:
                    prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                    marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                    marge_mois += marge_vente
                
                monthly_sales.append({
                    'year': debut_mois.year,
                    'month': debut_mois.month,
                    'date_debut': debut_mois,  # Ajout pour le tri
                    'month_name': debut_mois.strftime('%b %Y'),
                    'total_quantity': quantite_mois,
                    'total_revenue': revenue_mois,
                    'total_marge': marge_mois
                })
            
            # Tri décroissant par date pour avoir le mois actuel en premier
            monthly_sales.sort(key=lambda x: x['date_debut'], reverse=True)
            
            return {
                'product': product,
                'fournisseur_specifique': fournisseur_specifique,
                'sales_stats': sales_stats,
                'monthly_sales': monthly_sales,
                'lots_avec_marge': lots_avec_marge,
                'lots': lots.order_by('-date_reception')  # Tri cohérent
            }
        except Produit.DoesNotExist:
            return None
   
    @staticmethod
    def get_suppliers_with_stats():
        """Retourne la liste des fournisseurs avec leurs statistiques"""
        suppliers = Fournisseur.objects.all().order_by('nom')
        
        suppliers_with_stats = []
        for supplier in suppliers:
            lots = LotEntrepot.objects.filter(fournisseur=supplier)
            product_count = Produit.objects.filter(lots__fournisseur=supplier).distinct().count()
            
            total_stock = sum(lot.quantite_restante for lot in lots)
            total_valeur_stock_disponible = sum(
                lot.quantite_restante * (lot.prix_achat_unitaire or Decimal('0')) 
                for lot in lots
            )
            
            # Valeur d'achat total pour ce fournisseur
            valeur_achat_total = sum(
                lot.quantite_initiale * (lot.prix_achat_unitaire or Decimal('0'))
                for lot in lots
            )
            
            # Calcul de la marge générée par ce fournisseur (toutes périodes)
            ventes_fournisseur = Vente.objects.filter(
                detail_distribution__lot__fournisseur=supplier
            )
            marge_totale = Decimal('0')
            for vente in ventes_fournisseur:
                prix_achat = vente.detail_distribution.lot.prix_achat_unitaire or Decimal('0')
                marge_vente = (vente.prix_vente_unitaire - prix_achat) * vente.quantite
                marge_totale += marge_vente
            
            # Valeur des pertes pour ce fournisseur
            pertes_valeur = Decimal('0')
            for lot in lots:
                pertes_quantite = sum(perte.quantite_perdue for perte in lot.pertes.all())
                pertes_valeur += pertes_quantite * (lot.prix_achat_unitaire or Decimal('0'))
            
            suppliers_with_stats.append({
                'id': supplier.id,
                'nom': supplier.nom,
                'product_count': product_count,
                'total_lots': lots.count(),
                'total_stock': total_stock,
                'total_valeur_stock_disponible': total_valeur_stock_disponible,
                'valeur_achat_total': valeur_achat_total,
                'marge_generee': marge_totale,
                'pertes_valeur': pertes_valeur
            })
        
        return suppliers_with_stats