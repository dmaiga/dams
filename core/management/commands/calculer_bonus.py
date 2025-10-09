# core/management/commands/calculer_bonus.py
from django.core.management.base import BaseCommand
from core.models import Vente, Dette, BonusAgent
from datetime import timedelta

class Command(BaseCommand):
    help = 'Calcule les bonus pour toutes les ventes passées'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Calcul des bonus historiques...")
        
        total_bonus = 0
        
        # Ventes au comptant
        ventes_comptant = Vente.objects.filter(mode_paiement='comptant')
        for vente in ventes_comptant:
            bonus_agent, created = BonusAgent.objects.get_or_create(agent=vente.agent)
            ancien_total = bonus_agent.total_bonus
            bonus_agent.ajouter_produits_recouverts(vente.quantite)
            
            if bonus_agent.total_bonus > ancien_total:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {vente.agent.full_name}: {vente.quantite} produits comptant"
                    )
                )
                total_bonus += vente.quantite * 100
        
        # Crédits recouvrés sous 2 jours
        for dette in Dette.objects.filter(statut='paye'):
            if dette.date_reglement:
                delai = dette.date_reglement - dette.date_creation.date()
                if delai <= timedelta(days=2) and not dette.bonus_accorde:
                    produits = dette.accorder_bonus()
                    if produits > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ {dette.vente.agent.full_name}: {produits} produits crédit (2j)"
                            )
                        )
                        total_bonus += produits * 100
        
        self.stdout.write(
            self.style.SUCCESS(f"🎯 Total bonus calculé: {total_bonus} F")
        )