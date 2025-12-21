from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from core.models import DistributionAgent, DetailDistribution, MouvementStock, LotEntrepot, Agent

class DistributionService:
    
    @staticmethod
    def get_stock_disponible_produit(produit_nom):
        """Retourne le stock total disponible pour un produit (décimal)"""
        result = LotEntrepot.objects.filter(
            produit__nom=produit_nom,
            quantite_restante__gt=0
        ).aggregate(total=models.Sum('quantite_restante'))
        return result['total'] or Decimal('0.00')
    
    @staticmethod
    def get_lots_disponibles_produit(produit_nom):
        """Retourne tous les lots disponibles pour un produit"""
        return LotEntrepot.get_lots_disponibles_par_produit(produit_nom)
    
    @classmethod
    def valider_distribution_manuel(cls, data):
        """Valide une distribution avec sélection manuelle des lots et états"""
        produits_data = data.get('produits', [])
        
        for produit_data in produits_data:
            produit = produit_data['produit']
            lots_selectionnes = produit_data.get('lots_selectionnes', [])
            
            # Calculer la quantité totale demandée (décimale)
            quantite_totale_demandee = sum(
                Decimal(str(lot['quantite'])) for lot in lots_selectionnes
            )
            
            # Vérifier que la quantité totale ne dépasse pas le stock disponible
            stock_disponible = cls.get_stock_disponible_produit(produit.nom)
            if quantite_totale_demandee > stock_disponible:
                raise ValidationError(
                    f"Stock insuffisant pour {produit.nom}. "
                    f"Demandé: {quantite_totale_demandee}, Disponible: {stock_disponible}"
                )
            
            # Vérifier chaque lot sélectionné
            for lot_data in lots_selectionnes:
                lot_id = lot_data['lot_id']
                quantite = Decimal(str(lot_data['quantite']))
                etat_produit = lot_data.get('etat_produit', 'ENTIER')
                description_etat = lot_data.get('description_etat', '')
                
                try:
                    lot = LotEntrepot.objects.get(id=lot_id, produit=produit)
                    
                    # Vérifier la quantité
                    if quantite > lot.quantite_restante:
                        raise ValidationError(
                            f"Quantité trop élevée pour le lot {lot_id}. "
                            f"Demandé: {quantite}, Disponible: {lot.quantite_restante}"
                        )
                    
                    # Vérifier que la quantité est positive
                    if quantite <= Decimal('0.00'):
                        raise ValidationError(
                            f"Quantité doit être positive pour le lot {lot_id}. "
                            f"Quantité: {quantite}"
                        )
                    
                    # Validation de l'état du produit si spécifié
                    etats_valides = lot.get_etats_disponibles()
                    if etat_produit not in etats_valides:
                        raise ValidationError(
                            f"État '{etat_produit}' non valide pour {produit.nom}. "
                            f"États valides: {', '.join(etats_valides)}"
                        )
                        
                except LotEntrepot.DoesNotExist:
                    raise ValidationError(f"Lot {lot_id} non trouvé pour le produit {produit.nom}")
    
    @classmethod
    def creer_distribution_manuel(cls, data, current_user):
        """
        Crée une distribution avec sélection manuelle des lots et états
        """
        with transaction.atomic():
            # Validation
            cls._valider_donnees_distribution(data)
            cls.valider_distribution_manuel(data)
            
            # Récupérer ou créer le superviseur
            superviseur, _ = Agent.objects.get_or_create(
                user=current_user,
                defaults={'type_agent': 'entrepot'}
            )
            
            # Créer la distribution
            distribution = DistributionAgent.objects.create(
                superviseur=superviseur,
                agent_terrain=data.get('agent_terrain'),
                type_distribution=data['type_distribution'],
                date_distribution=data['date_distribution'],
                est_retroactive=data['date_distribution'] < timezone.now(),
                description=data.get('description', '')
            )
            
            # Traiter les produits avec lots sélectionnés manuellement
            produits_data = data.get('produits', [])
            details_creation = []
            mouvements_creation = []
            lots_a_mettre_a_jour = []
            
            for produit_data in produits_data:
                produit = produit_data['produit']
                prix_gros = produit_data.get('prix_gros')
                prix_detail = produit_data.get('prix_detail')
                lots_selectionnes = produit_data.get('lots_selectionnes', [])
                
                for lot_data in lots_selectionnes:
                    lot_id = lot_data['lot_id']
                    quantite = Decimal(str(lot_data['quantite']))
                    etat_produit = lot_data.get('etat_produit', 'ENTIER')
                    description_etat = lot_data.get('description_etat', '')
                    
                    # Récupérer le lot
                    lot = LotEntrepot.objects.get(id=lot_id)
                    
                    # Créer le détail de distribution avec état
                    details_creation.append(DetailDistribution(
                        distribution=distribution,
                        lot=lot,
                        quantite=quantite,
                        etat_produit=etat_produit,
                        description_etat=description_etat,
                        prix_gros=prix_gros,
                        prix_detail=prix_detail
                    ))
                    
                    # Préparer la mise à jour du lot
                    lots_a_mettre_a_jour.append((lot.id, quantite))
                    
                    # Préparer le mouvement de stock avec description de l'état
                    description_mouvement = f"DISTRIBUTION - {etat_produit}"
                    if description_etat:
                        description_mouvement += f" ({description_etat})"
                    
                    mouvements_creation.append(MouvementStock(
                        produit=produit,
                        lot=lot,
                        agent=superviseur,
                        type_mouvement='DISTRIBUTION',
                        quantite=quantite,
                        date_mouvement=data['date_distribution'],
                        description=description_mouvement
                    ))
            
            # Création en masse
            DetailDistribution.objects.bulk_create(details_creation)
            
            # Mise à jour des lots (décimale)
            for lot_id, quantite in lots_a_mettre_a_jour:
                LotEntrepot.objects.filter(id=lot_id).update(
                    quantite_restante=models.F('quantite_restante') - quantite
                )
            
            # Création des mouvements de stock
            MouvementStock.objects.bulk_create(mouvements_creation)
            
            # Mettre à jour les totaux
            cls._mettre_a_jour_totaux_distribution(distribution)
            
            return distribution
    
    @staticmethod
    def _valider_donnees_distribution(data):
        """Valide les données de base de la distribution"""
        type_distribution = data.get('type_distribution')
        agent_terrain = data.get('agent_terrain')
        date_distribution = data.get('date_distribution')
        
        if type_distribution in ['TERRAIN', 'STAGIAIRE'] and not agent_terrain:
            raise ValidationError('Un agent est requis pour ce type de distribution.')
        
        if type_distribution == 'STAGIAIRE' and agent_terrain:
            if agent_terrain.type_agent != 'stagiaire':
                raise ValidationError('Vous devez sélectionner un stagiaire.')
            elif hasattr(agent_terrain, 'date_fin_stage') and agent_terrain.date_fin_stage < timezone.now().date():
                raise ValidationError('Ce stagiaire est expiré.')
        
        if date_distribution and date_distribution > timezone.now():
            raise ValidationError('La date de distribution ne peut pas être dans le futur')
    
    @staticmethod
    def _mettre_a_jour_totaux_distribution(distribution):
        """Met à jour les totaux d'une distribution (décimaux)"""
        from decimal import Decimal
        
        details = distribution.detaildistribution_set.filter(est_supprime=False)
        
        quantite_totale = sum(
            Decimal(str(detail.quantite)) for detail in details
        )
        
        valeur_gros_totale = sum(
            (detail.prix_gros or Decimal('0.00')) * Decimal(str(detail.quantite)) 
            for detail in details
        )
        
        valeur_detail_totale = sum(
            (detail.prix_detail or Decimal('0.00')) * Decimal(str(detail.quantite)) 
            for detail in details
        )
        
        nombre_produits_differents = details.values('lot__produit').distinct().count()
        
        distribution.quantite_totale = quantite_totale
        distribution.valeur_gros_totale = valeur_gros_totale
        distribution.valeur_detail_totale = valeur_detail_totale
        distribution.nombre_produits_differents = nombre_produits_differents
        distribution.save()