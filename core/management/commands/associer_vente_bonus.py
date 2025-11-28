from django.core.management.base import BaseCommand
from core.models import Recouvrement, Vente
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from decimal import Decimal

class Command(BaseCommand):
    help = 'Associe les recouvrements aux ventes par cumul journalier'

    def handle(self, *args, **options):
        recouvrements_sans_vente = Recouvrement.objects.filter(vente__isnull=True)
        
        self.stdout.write(f"🔍 Trouvé {recouvrements_sans_vente.count()} recouvrements sans vente associée")
        
        associations_reussies = 0
        associations_echouees = 0
        
        for recouvrement in recouvrements_sans_vente:
            self.stdout.write(f"\n--- Traitement du Recouvrement {recouvrement.id} ---")
            self.stdout.write(f"Agent: {recouvrement.agent.full_name}")
            self.stdout.write(f"Montant: {recouvrement.montant_recouvre} FCFA")
            self.stdout.write(f"Date recouvrement: {recouvrement.date_recouvrement.date()}")
            
            # Étape 1: Chercher par cumul journalier sur 7 jours
            association_trouvee = self.associer_par_cumul_journalier(recouvrement)
            
            if association_trouvee:
                associations_reussies += 1
            else:
                associations_echouees += 1
        
        # Résumé final
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write("📊 RÉSUMÉ FINAL")
        self.stdout.write(f"✅ Associations réussies: {associations_reussies}")
        self.stdout.write(f"❌ Associations échouées: {associations_echouees}")
        self.stdout.write(f"🔧 Prochaine étape: Exécuter 'recalculer_bonus_passés'")

    def associer_par_cumul_journalier(self, recouvrement):
        """Associe un recouvrement aux ventes par cumul journalier"""
        
        # Recherche sur 7 jours avant la date du recouvrement
        date_debut = recouvrement.date_recouvrement.date() - timedelta(days=7)
        date_fin = recouvrement.date_recouvrement.date()
        
        self.stdout.write(f"📅 Recherche des ventes du {date_debut} au {date_fin}")
        
        # Récupérer toutes les ventes de l'agent dans la période
        ventes_periode = Vente.objects.filter(
            agent=recouvrement.agent,
            date_vente__date__range=[date_debut, date_fin]
        ).exclude(recouvrements__isnull=False)  # Exclure les ventes déjà recouvrées
        
        if not ventes_periode.exists():
            self.stdout.write("❌ Aucune vente trouvée dans la période")
            return False
        
        # Grouper les ventes par jour et calculer les totaux
        ventes_par_jour = {}
        for vente in ventes_periode:
            jour = vente.date_vente.date()
            if jour not in ventes_par_jour:
                ventes_par_jour[jour] = []
            ventes_par_jour[jour].append(vente)
        
        # Afficher les totaux par jour
        self.stdout.write("📊 Totaux par jour trouvés:")
        for jour, ventes_du_jour in ventes_par_jour.items():
            total_jour = sum(vente.total_vente for vente in ventes_du_jour)
            self.stdout.write(f"  {jour}: {len(ventes_du_jour)} ventes = {total_jour} FCFA")
        
        # Chercher le jour où le total correspond exactement au recouvrement
        for jour, ventes_du_jour in ventes_par_jour.items():
            total_jour = sum(vente.total_vente for vente in ventes_du_jour)
            
            # Vérifier la correspondance exacte
            if abs(total_jour - recouvrement.montant_recouvre) < Decimal('0.01'):
                self.stdout.write(f"🎯 CORRESPONDANCE TROUVÉE pour le {jour}")
                
                # Associer le recouvrement à toutes les ventes de cette journée
                for vente in ventes_du_jour:
                    recouvrement.vente = vente
                    # Pour garder la relation OneToOne, on crée un nouveau recouvrement pour chaque vente
                    nouveau_recouvrement = Recouvrement.objects.create(
                        agent=recouvrement.agent,
                        superviseur=recouvrement.superviseur,
                        vente=vente,
                        montant_recouvre=vente.total_vente,  # Montant de la vente individuelle
                        date_recouvrement=recouvrement.date_recouvrement,
                        commentaire=f"Association automatique - Cumul du {jour}",
                        bonus_accorde=False,
                        montant_bonus=0
                    )
                    self.stdout.write(f"  ✅ Vente {vente.id} associée (Recouvrement {nouveau_recouvrement.id})")
                
                # Marquer l'ancien recouvrement comme associé (ou le supprimer)
                recouvrement.delete()
                return True
        
        self.stdout.write(f"❌ Aucun cumul journalier ne correspond au montant {recouvrement.montant_recouvre}")
        return False