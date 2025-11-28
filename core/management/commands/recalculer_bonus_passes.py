from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Recouvrement, BonusAgent, Vente
from decimal import Decimal

class Command(BaseCommand):
    help = 'Recalcule tous les bonus des recouvrements passés selon la nouvelle logique'

    def add_arguments(self, parser):
        parser.add_argument(
            '--agent-id',
            type=int,
            help='Recalculer uniquement pour un agent spécifique',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simuler le recalcul sans sauvegarder',
        )

    def handle(self, *args, **options):
        agent_id = options.get('agent_id')
        dry_run = options.get('dry_run')
        
        # Filtrer les recouvrements AVEC vente associée
        recouvrements = Recouvrement.objects.filter(vente__isnull=False)
        if agent_id:
            recouvrements = recouvrements.filter(agent_id=agent_id)
        
        recouvrements = recouvrements.select_related('agent', 'vente')
        
        total_bonus_accorde = 0
        total_recouvrements_traites = 0
        
        self.stdout.write(f"🔍 Analyse de {recouvrements.count()} recouvrements avec vente associée...")
        
        for recouvrement in recouvrements:
            # Vérifier l'éligibilité au bonus
            delai_vente_recouvrement = recouvrement.date_recouvrement - recouvrement.vente.date_vente
            eligible = delai_vente_recouvrement <= timedelta(hours=48)
            
            bonus_calcule = recouvrement.vente.quantite * 100 if eligible else 0
            
            ancien_bonus = recouvrement.montant_bonus
            ancien_statut = recouvrement.bonus_accorde
            
            if dry_run:
                self.stdout.write(
                    f"📊 Recouvrement {recouvrement.id}: "
                    f"Vente du {recouvrement.vente.date_vente.strftime('%d/%m/%Y %H:%M')} → "
                    f"Recouvrement du {recouvrement.date_recouvrement.strftime('%d/%m/%Y %H:%M')} → "
                    f"Délai: {delai_vente_recouvrement} → "
                    f"Éligible: {eligible} → "
                    f"Bonus: {bonus_calcule} FCFA"
                )
            else:
                # Mettre à jour le recouvrement
                recouvrement.montant_bonus = bonus_calcule
                recouvrement.bonus_accorde = eligible
                recouvrement.save()
                
                # Mettre à jour le bonus de l'agent
                if eligible and bonus_calcule > 0:
                    bonus_agent, created = BonusAgent.objects.get_or_create(
                        agent=recouvrement.agent,
                        defaults={'total_bonus': 0, 'nombre_produits_recouverts': 0}
                    )
                    if not created:
                        # Pour l'instant on réinitialise, mais on pourrait faire plus intelligent
                        bonus_agent.total_bonus = Decimal('0.00')
                        bonus_agent.nombre_produits_recouverts = 0
                        bonus_agent.save()
                    
                    # Ajouter le bonus
                    bonus_agent.ajouter_bonus(bonus_calcule)
                    total_bonus_accorde += bonus_calcule
                
                total_recouvrements_traites += 1
                
                if ancien_bonus != bonus_calcule or ancien_statut != eligible:
                    self.stdout.write(
                        f"✅ Recouvrement {recouvrement.id} mis à jour: "
                        f"{ancien_bonus} → {bonus_calcule} FCFA "
                        f"({ancien_statut} → {eligible})"
                    )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"🎉 Recalcul terminé! "
                    f"{total_recouvrements_traites} recouvrements traités, "
                    f"{total_bonus_accorde} FCFA de bonus accordés au total"
                )
            )
        else:
            self.stdout.write("🔍 Simulation terminée - Aucune modification en base")