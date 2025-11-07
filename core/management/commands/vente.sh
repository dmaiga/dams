# Dans le shell Django (python manage.py shell)
from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import Vente, Agent, Client, DetailDistribution, Dette
from django.db import transaction

def creer_ventes_agent(agent_username):
    """
    Crée les ventes pour un agent spécifique
    """
    try:
        # Récupérer l'agent
        agent = Agent.objects.get(user__username=agent_username)
        client_inconnu, _ = Client.objects.get_or_create(
            nom="Client Inconnu",
            defaults={'contact': 'Non specifie', 'type_client':'particulier'}
        )
        
        print(f"🚀 CRÉATION DES VENTES POUR: {agent.full_name}")
        print(f"📧 Username: {agent_username}")
        print(f"🏷️ Type: {agent.get_type_agent_display()}")
        print("=" * 50)
        
        # Afficher les distributions disponibles pour cet agent
        distributions = DetailDistribution.objects.filter(
            distribution__agent_terrain=agent
        ).select_related('lot__produit')
        
        print("📦 DISTRIBUTIONS DISPONIBLES:")
        for dist in distributions:
            print(f"   • {dist.lot.produit.nom}: {dist.quantite} unités "
                  f"(Gros: {dist.prix_gros} FCFA, Détail: {dist.prix_detail} FCFA)")
        
        # CONFIGURATION DES VENTES - MODIFIEZ ICI POUR CHAQUE AGENT
        ventes_config = [
{
                'produit': 'ail',
                'quantite': 25,
                'type_vente': 'gros',  # 'gros' ou 'detail'
                'mode_paiement': 'comptant',  # 'comptant' ou 'credit'
                'date_vente': '18/09/2025',
	
               
            },
                        {
                'produit': 'ail',
                'quantite': 10,
                'type_vente': 'gros',  # 'gros' ou 'detail'
                'mode_paiement': 'comptant',  # 'comptant' ou 'credit'
                'date_vente': '19/09/2025',
		
            },


        ]
        
        print(f"\n🛒 VENTES À CRÉER POUR {agent.full_name}:")
        for i, vente_config in enumerate(ventes_config, 1):
            print(f"   {i}. {vente_config['quantite']} {vente_config['produit']} "
                  f"({vente_config['type_vente']}) - {vente_config['mode_paiement']} "
                  f"le {vente_config['date_vente']}")
        
        confirmation = input("\n❓ Confirmez-vous la création de ces ventes? (oui/non): ")
        if confirmation.lower() != 'oui':
            print("❌ Annulation des ventes")
            return []
        
        with transaction.atomic():
            ventes_crees = []
            
            for vente_config in ventes_config:
                print(f"\n🎯 Création vente: {vente_config['quantite']} {vente_config['produit']}...")
                
                # Trouver la distribution correspondante
                detail_distrib = DetailDistribution.objects.filter(
                    distribution__agent_terrain=agent,
                    lot__produit__nom=vente_config['produit']
                ).first()
                
                if detail_distrib:
                    if detail_distrib.quantite >= vente_config['quantite']:
                        # Convertir la date
                        date_vente = timezone.make_aware(
                            datetime.strptime(vente_config['date_vente'], '%d/%m/%Y')
                        )
                        
                        # Créer la vente
                        vente = Vente.objects.create(
                            agent=agent,
                            client=client_inconnu,
                            detail_distribution=detail_distrib,
                            quantite=vente_config['quantite'],
                            type_vente=vente_config['type_vente'],
                            mode_paiement=vente_config['mode_paiement'],
                            date_vente=date_vente,
                            prix_vente_unitaire=vente_config.get('prix_vente')
                        )
                        
                        ventes_crees.append(vente)
                        
                        print(f"✅ VENTE CRÉÉE:")
                        print(f"   📦 Produit: {vente.produit_nom}")
                        print(f"   🏷️ Type: {vente.get_type_vente_display()}")
                        print(f"   💰 Prix unitaire: {vente.prix_vente_unitaire} FCFA")
                        print(f"   📊 Quantité: {vente.quantite}")
                        print(f"   💵 Total: {vente.total_vente} FCFA")
                        print(f"   💳 Paiement: {vente.mode_paiement}")
                        print(f"   📅 Date: {vente.date_vente.strftime('%d/%m/%Y')}")
                        
                        if vente.mode_paiement == 'credit':
                            print(f"   🏦 Dette créée: {vente.dette_associee.montant_total} FCFA")
                            
                        if vente.eligible_bonus_vente_comptant:
                            print(f"   🏆 Bonus: {vente.bonus_vente_comptant} FCFA")
                            
                    else:
                        print(f"❌ Stock insuffisant: {detail_distrib.quantite} disponible, "
                              f"{vente_config['quantite']} demandé")
                else:
                    print(f"❌ Aucune distribution trouvée pour {vente_config['produit']}")
            
            # RÉCAPITULATIF
            if ventes_crees:
                print("\n" + "=" * 50)
                print(f"🎉 VENTES TERMINÉES POUR {agent.full_name}!")
                print("=" * 50)
                
                total_ventes = sum(v.total_vente for v in ventes_crees)
                ventes_comptant = [v for v in ventes_crees if v.mode_paiement == 'comptant']
                ventes_credit = [v for v in ventes_crees if v.mode_paiement == 'credit']
                bonus_total = sum(v.bonus_vente_comptant for v in ventes_comptant)
                
                print(f"💰 Chiffre d'affaires: {total_ventes} FCFA")
                print(f"📦 Nombre de ventes: {len(ventes_crees)}")
                print(f"💵 Comptant: {len(ventes_comptant)} ventes")
                print(f"💳 Crédit: {len(ventes_credit)} ventes") 
                print(f"🏆 Bonus: {bonus_total} FCFA")
                print(f"📅 Période: {ventes_crees[0].date_vente.strftime('%d/%m/%Y')} "
                      f"à {ventes_crees[-1].date_vente.strftime('%d/%m/%Y')}")
            
            return ventes_crees
            
    except Agent.DoesNotExist:
        print(f"❌ Agent '{agent_username}' non trouvé")
        return []
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return []

# EXÉCUTION PAR AGENT - MODIFIEZ LE USERNAME POUR CHAQUE AGENT