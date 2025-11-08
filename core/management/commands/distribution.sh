# Dans le shell Django (python manage.py shell)
from django.db import models
from django.utils import timezone
from datetime import datetime
from core.models import LotEntrepot, Agent, DistributionAgent, DetailDistribution
from django.db import transaction

def creer_distributions_multiple():
    try:
        with transaction.atomic():
            print("🚀 DÉBUT DES DISTRIBUTIONS MULTIPLES...")
            
            # 1. Récupération des agents
            superviseur = Agent.objects.get(user__username='abdoulaye.kone')
            mankoulako = Agent.objects.get(user__username='mankoulako.sidibe')
            abdoulaye = Agent.objects.get(user__username='abdoulaye.kone')
            alpha = Agent.objects.get(user__username='alpha.diallo')
            fatoumata = Agent.objects.get(user__username='fatoumata.kouyate')
            koniba = Agent.objects.get(user__username='koniba.daou')
            
            # 2. CONFIGURATION DES DISTRIBUTIONS MULTIPLES
            distributions_config = [
                
                 {
                    'date': '29/08/2025', 
                    'produit': 'ail',
                    'prix_gros': 11000,
                    'prix_detail': 12500,
                    'distributions': [                                                   
                        (alpha, 1, "Alpha"),                     
                        (abdoulaye, 7, "Abdoulaye(Auto)"), 

                    ]
                },
                 {
                    'date': '30/08/2025', 
                    'produit': 'ail',
                    'prix_gros': 11000,
                    'prix_detail': 12500,
                    'distributions': [

                       
                        (fatoumata, 2, "Fatoumata"),                                                    
                        (alpha, 1, "Alpha"),  
                        (abdoulaye, 2, "Abdoulaye(Auto)"), 

                    ]
                },
                                 {
                    'date': '01/09/2025', 
                    'produit': 'ail',
                    'prix_gros': 11000,
                    'prix_detail': 12500,
                    'distributions': [

                        
                        (fatoumata, 2, "Fatoumata"),                                                    
                        (alpha, 1, "Alpha"),  
                        (abdoulaye, 1, "Abdoulaye(Auto)"), 

                    ]
                },
                                 {
                    'date': '02/09/2025', 
                    'produit': 'ail',
                    'prix_gros': 11000,
                    'prix_detail': 12500,
                    'distributions': [
                        (fatoumata, 1, "Fatoumata"),                                                    
                        (alpha, 1, "Alpha"),   
                        (abdoulaye, 1, "Abdoulaye(Auto)"), 

                    ]
                },
               
            
            ]
            
            toutes_distributions = []
            
            for config in distributions_config:
                # Conversion de la date
                date_distribution = datetime.strptime(config['date'], '%d/%m/%Y')
                date_distribution = timezone.make_aware(date_distribution)
                
                print(f"\n{'='*60}")
                print(f"📅 DISTRIBUTION DU {config['date']}")
                print(f"📦 Produit: {config['produit']}")
                print(f"💰 Prix gros: {config['prix_gros']} FCFA")
                print(f"💰 Prix détail: {config['prix_detail']} FCFA")
                print(f"{'='*60}")
                
                distributions_crees = []
                
                for agent, quantite, nom in config['distributions']:
                    print(f"\n🎯 Distribution à {nom}: {quantite} unités...")
                    
                    # Trouver un lot disponible
                    lot = LotEntrepot.objects.filter(
                        produit__nom=config['produit'],
                        quantite_restante__gte=quantite
                    ).order_by('date_reception').first()
                    
                    if lot:
                        # Créer distribution avec date rétroactive
                        distrib = DistributionAgent.objects.create(
                            superviseur=superviseur,
                            agent_terrain=agent,
                            date_distribution=date_distribution,
                            est_retroactive=True
                        )
                        
                        # Créer détail
                        DetailDistribution.objects.create(
                            distribution=distrib,
                            lot=lot,
                            quantite=quantite,
                            prix_gros=config['prix_gros'],
                            prix_detail=config['prix_detail']
                        )
                        
                        # Mettre à jour stock
                        lot.quantite_restante -= quantite
                        lot.save()
                        
                        # Mettre à jour totaux
                        distrib._mettre_a_jour_totaux()
                        
                        distributions_crees.append(distrib)
                        print(f"✅ Succès - Stock restant du lot: {lot.quantite_restante}")
                        
                        # Afficher info auto-distribution
                        if agent == superviseur:
                            print("   🤖 AUTO-DISTRIBUTION du superviseur")
                    else:
                        print(f"❌ Échec - Stock insuffisant de {config['produit']} pour {nom}")
                
                toutes_distributions.extend(distributions_crees)
                
                # Récapitulatif pour cette date
                total_date = sum(distrib.quantite_totale for distrib in distributions_crees)
                print(f"\n📊 RÉCAPITULATIF {config['date']}:")
                print(f"   📦 Distribué: {total_date} unités")
                print(f"   👥 Distributions: {len(distributions_crees)}")
            
            # 3. RÉCAPITULATIF GÉNÉRAL
            print("\n" + "="*60)
            print("🎉 TOUTES LES DISTRIBUTIONS TERMINÉES AVEC SUCCÈS!")
            print("="*60)
            
            # Statistiques par produit
            produits_distribues = set()
            for distrib in toutes_distributions:
                for detail in distrib.detaildistribution_set.all():
                    produits_distribues.add(detail.lot.produit.nom)
            
            print(f"\n📈 STATISTIQUES GÉNÉRALES:")
            print(f"📦 Total distributions créées: {len(toutes_distributions)}")
            print(f"🎯 Produits distribués: {', '.join(produits_distribues)}")
            
            # Détail par produit
            print(f"\n📊 STOCK RESTANT PAR PRODUIT:")
            for produit in produits_distribues:
                stock_restant = LotEntrepot.objects.filter(
                    produit__nom=produit
                ).aggregate(total=models.Sum('quantite_restante'))['total'] or 0
                print(f"   • {produit}: {stock_restant} unités")
            
            # Détail des distributions créées
            print(f"\n👥 RÉCAPITULATIF DES DISTRIBUTIONS:")
            for distrib in toutes_distributions:
                produit_nom = distrib.detaildistribution_set.first().lot.produit.nom
                type_distrib = "🤖 Auto" if distrib.agent_terrain == superviseur else "👥 Terrain"
                print(f"   • {type_distrib} {distrib.agent_terrain.full_name}: "
                      f"{distrib.quantite_totale} {produit_nom} "
                      f"le {distrib.date_distribution.strftime('%d/%m/%Y')}")
                      
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

# Exécuter la fonction
creer_distributions_multiple()