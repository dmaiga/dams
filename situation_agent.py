#!/usr/bin/env python
"""
Script de génération de rapport des ventes par agent
Période du 20/10/2025 au 20/11/2025
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dams.settings')
django.setup()

from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce

from core.models import Vente, Recouvrement, Agent

class RapportVentes:
    def __init__(self, date_debut, date_fin):
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.resultats = []
        
    def generer_rapport(self):
        """Génère le rapport complet"""
        print("=" * 100)
        print("RAPPORT DES VENTES PAR AGENT")
        print(f"Période du {self.date_debut.strftime('%d/%m/%Y')} au {self.date_fin.strftime('%d/%m/%Y')}")
        print("=" * 100)
        
        # Récupération des agents ayant fait des ventes dans la période
        agents_actifs = Agent.objects.filter(
            vente__date_vente__range=[self.date_debut, self.date_fin],
            vente__stagiaire__isnull=True  # Ventes personnelles seulement
        ).distinct()
        
        if not agents_actifs:
            print("Aucune vente trouvée dans la période spécifiée.")
            return
        
        print(f"\nNombre d'agents actifs: {agents_actifs.count()}")
        print("-" * 100)
        
        # Analyse pour chaque agent
        for agent in agents_actifs:
            self.analyser_agent(agent)
        
        # Affichage des résultats détaillés
        self.afficher_resultats_detailles()
        
        # Résumé global
        self.afficher_resume_global()
        
        # Export optionnel vers fichier
        self.exporter_vers_fichier()
    
    def analyser_agent(self, agent):
        """Analyse les ventes et recouvrements d'un agent"""
        # Récupération des ventes personnelles de l'agent
        ventes_agent = Vente.objects.filter(
            agent=agent,
            date_vente__range=[self.date_debut, self.date_fin],
            stagiaire__isnull=True
        ).select_related('detail_distribution')
        
        if not ventes_agent:
            return
        
        # Séparation par type de vente
        ventes_gros = ventes_agent.filter(type_vente='gros')
        ventes_detail = ventes_agent.filter(type_vente='detail')
        
        # Calcul des statistiques
        stats_gros = self.calculer_statistiques_type_vente(agent, ventes_gros, 'gros')
        stats_detail = self.calculer_statistiques_type_vente(agent, ventes_detail, 'detail')
        
        # Stockage des résultats
        self.resultats.append({
            'agent': agent.full_name,
            'type_agent': agent.get_type_agent_display(),
            'gros': stats_gros,
            'detail': stats_detail,
            'total_ventes': ventes_agent.count(),
            'total_cartons': (stats_gros['quantite_totale'] + stats_detail['quantite_totale'])
        })
    
    def calculer_statistiques_type_vente(self, agent, ventes_query, type_vente):
        """Calcule les statistiques pour un type de vente spécifique"""
        quantite_totale = ventes_query.aggregate(
            total=Coalesce(Sum('quantite'), Decimal('0.00'))
        )['total']
        
        ventes_recouvertes = 0
        ventes_non_recouvertes = 0
        quantite_recouverte = Decimal('0.00')
        quantite_non_recouverte = Decimal('0.00')
        montant_recouvert = Decimal('0.00')
        montant_non_recouvert = Decimal('0.00')
        
        for vente in ventes_query:
            # Vérification du recouvrement dans les 2 jours
            recouvrement_dans_delai = Recouvrement.objects.filter(
                agent=agent,
                date_recouvrement__range=[
                    vente.date_vente,
                    vente.date_vente + timedelta(days=2)
                ],
                montant_recouvre__gte=vente.total_vente
            ).exists()
            
            if recouvrement_dans_delai:
                ventes_recouvertes += 1
                quantite_recouverte += vente.quantite
                montant_recouvert += vente.total_vente
            else:
                ventes_non_recouvertes += 1
                quantite_non_recouverte += vente.quantite
                montant_non_recouvert += vente.total_vente
        
        return {
            'quantite_totale': quantite_totale,
            'ventes_recouvertes': ventes_recouvertes,
            'ventes_non_recouvertes': ventes_non_recouvertes,
            'quantite_recouverte': quantite_recouverte,
            'quantite_non_recouverte': quantite_non_recouverte,
            'montant_recouvert': montant_recouvert,
            'montant_non_recouvert': montant_non_recouvert,
            'taux_recouvrement_quantite': (quantite_recouverte / quantite_totale * 100) if quantite_totale > 0 else 0,
            'taux_recouvrement_ventes': (ventes_recouvertes / (ventes_recouvertes + ventes_non_recouvertes) * 100) if (ventes_recouvertes + ventes_non_recouvertes) > 0 else 0
        }
    
    def afficher_resultats_detailles(self):
        """Affiche les résultats détaillés par agent"""
        print("\n" + "=" * 100)
        print("DÉTAIL PAR AGENT")
        print("=" * 100)
        
        for resultat in self.resultats:
            print(f"\n🔹 AGENT: {resultat['agent']}")
            print(f"   Type: {resultat['type_agent']}")
            print(f"   Total ventes: {resultat['total_ventes']}")
            print(f"   Total cartons: {resultat['total_cartons']:.2f}")
            print(f"   {'─' * 50}")
            
            # Affichage gros
            gros = resultat['gros']
            print(f"   📦 VENTES EN GROS:")
            print(f"      • Cartons vendus: {gros['quantite_totale']:.2f}")
            print(f"      • Ventes recouvertes: {gros['ventes_recouvertes']}/{gros['ventes_recouvertes'] + gros['ventes_non_recouvertes']}")
            print(f"      • Quantité recouverte: {gros['quantite_recouverte']:.2f} ({gros['taux_recouvrement_quantite']:.1f}%)")
            print(f"      • Montant recouvré: {gros['montant_recouvert']:,.0f} FCFA")
            
            # Affichage détail
            detail = resultat['detail']
            print(f"   🛒 VENTES AU DÉTAIL:")
            print(f"      • Cartons vendus: {detail['quantite_totale']:.2f}")
            print(f"      • Ventes recouvertes: {detail['ventes_recouvertes']}/{detail['ventes_recouvertes'] + detail['ventes_non_recouvertes']}")
            print(f"      • Quantité recouverte: {detail['quantite_recouverte']:.2f} ({detail['taux_recouvrement_quantite']:.1f}%)")
            print(f"      • Montant recouvré: {detail['montant_recouvert']:,.0f} FCFA")
            
            print(f"   {'─' * 50}")
            print(f"   📊 PERFORMANCE GLOBALE:")
            total_recouvrement = (gros['taux_recouvrement_quantite'] + detail['taux_recouvrement_quantite']) / 2
            print(f"      • Taux de recouvrement moyen: {total_recouvrement:.1f}%")
    
    def afficher_resume_global(self):
        """Affiche le résumé global"""
        print("\n" + "=" * 100)
        print("RÉSUMÉ GLOBAL")
        print("=" * 100)
        
        # Calcul des totaux
        total_cartons_gros = sum(r['gros']['quantite_totale'] for r in self.resultats)
        total_cartons_detail = sum(r['detail']['quantite_totale'] for r in self.resultats)
        total_cartons_recouverts_gros = sum(r['gros']['quantite_recouverte'] for r in self.resultats)
        total_cartons_recouverts_detail = sum(r['detail']['quantite_recouverte'] for r in self.resultats)
        total_montant_recouvert_gros = sum(r['gros']['montant_recouvert'] for r in self.resultats)
        total_montant_recouvert_detail = sum(r['detail']['montant_recouvert'] for r in self.resultats)
        
        print(f"\n📈 CHIFFRES CLÉS:")
        print(f"   • Total cartons vendus: {total_cartons_gros + total_cartons_detail:,.2f}")
        print(f"   • Total cartons recouverts: {total_cartons_recouverts_gros + total_cartons_recouverts_detail:,.2f}")
        print(f"   • Total montant recouvré: {total_montant_recouvert_gros + total_montant_recouvert_detail:,.0f} FCFA")
        
        print(f"\n📦 VENTES EN GROS:")
        print(f"   • Cartons vendus: {total_cartons_gros:,.2f}")
        print(f"   • Cartons recouverts: {total_cartons_recouverts_gros:,.2f}")
        print(f"   • Taux de recouvrement: {(total_cartons_recouverts_gros/total_cartons_gros*100) if total_cartons_gros > 0 else 0:.1f}%")
        print(f"   • Montant recouvré: {total_montant_recouvert_gros:,.0f} FCFA")
        
        print(f"\n🛒 VENTES AU DÉTAIL:")
        print(f"   • Cartons vendus: {total_cartons_detail:,.2f}")
        print(f"   • Cartons recouverts: {total_cartons_recouverts_detail:,.2f}")
        print(f"   • Taux de recouvrement: {(total_cartons_recouverts_detail/total_cartons_detail*100) if total_cartons_detail > 0 else 0:.1f}%")
        print(f"   • Montant recouvré: {total_montant_recouvert_detail:,.0f} FCFA")
        
        # Classement des agents
        print(f"\n🏆 CLASSEMENT DES AGENTS (par quantité recouverte):")
        agents_classes = sorted(
            self.resultats, 
            key=lambda x: (x['gros']['quantite_recouverte'] + x['detail']['quantite_recouverte']), 
            reverse=True
        )
        
        for i, agent in enumerate(agents_classes[:5], 1):  # Top 5
            total_recouvert = agent['gros']['quantite_recouverte'] + agent['detail']['quantite_recouverte']
            print(f"   {i}. {agent['agent']}: {total_recouvert:.2f} cartons recouverts")
    
    def exporter_vers_fichier(self):
        """Exporte le rapport vers un fichier texte"""
        nom_fichier = f"rapport_ventes_{self.date_debut.strftime('%Y%m%d')}_{self.date_fin.strftime('%Y%m%d')}.txt"
        
        with open(nom_fichier, 'w', encoding='utf-8') as f:
            # Rediriger la sortie standard vers le fichier
            import contextlib
            
            class StreamToFile:
                def __init__(self, file):
                    self.file = file
                
                def write(self, text):
                    self.file.write(text)
                    # Afficher aussi dans la console
                    print(text, end='')
            
            old_stdout = sys.stdout
            sys.stdout = StreamToFile(f)
            
            # Regénérer l'affichage
            print("=" * 100)
            print("RAPPORT DES VENTES PAR AGENT (EXPORT)")
            print(f"Période du {self.date_debut.strftime('%d/%m/%Y')} au {self.date_fin.strftime('%d/%m/%Y')}")
            print(f"Généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}")
            print("=" * 100)
            
            self.afficher_resultats_detailles()
            self.afficher_resume_global()
            
            sys.stdout = old_stdout
        
        print(f"\n💾 Rapport exporté dans: {nom_fichier}")

def main():
    """Fonction principale"""
    try:
        # Définition de la période
        date_debut = datetime(2025, 10, 20)
        date_fin = datetime(2025, 11, 20, 23, 59, 59)
        
        # Vérification que la date de fin est après la date de début
        if date_fin <= date_debut:
            print("❌ Erreur: La date de fin doit être après la date de début.")
            return
        
        # Génération du rapport
        rapport = RapportVentes(date_debut, date_fin)
        rapport.generer_rapport()
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération du rapport: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()