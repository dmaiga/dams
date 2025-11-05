# management/commands/corriger_api.py
from django.core.management.base import BaseCommand
from django.db.models import Sum
from core.models import LotEntrepot, DetailDistribution

class Command(BaseCommand):
    help = 'Corrige les quantités restantes des lots basé sur les distributions réelles'

    def handle(self, *args, **options):
        self.stdout.write("Correction des quantités restantes des lots...")
        
        lots = LotEntrepot.objects.all()
        total_corriges = 0
        
        for lot in lots:
            # Calculer la quantité réellement distribuée
            quantite_distribuee = DetailDistribution.objects.filter(
                lot=lot,
                distribution__est_supprime=False,
                est_supprime=False
            ).aggregate(total=Sum('quantite'))['total'] or 0
            
            # Nouvelle quantité restante
            nouvelle_quantite = lot.quantite_initiale - quantite_distribuee
            
            if lot.quantite_restante != nouvelle_quantite:
                self.stdout.write(
                    f"Lot {lot.id} ({lot.produit.nom}): "
                    f"{lot.quantite_restante} → {nouvelle_quantite}"
                )
                lot.quantite_restante = nouvelle_quantite
                lot.save()
                total_corriges += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"Correction terminée: {total_corriges} lots corrigés sur {lots.count()}"
        ))