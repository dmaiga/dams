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
            champ = Agent.objects.get(user__username='agent.champ')
            massira = Agent.objects.get(user__username='massira.doumbia')
            anna = Agent.objects.get(user__username='anna.coulibaly')
            sali = Agent.objects.get(user__username='sali.sangare')
            kadiatou = Agent.objects.get(user__username='kadiatou.doumbia')
            moussony = Agent.objects.get(user__username='moussony.konate')
            djenebaS = Agent.objects.get(user__username='djeneba.sidibe')
            djenebaY = Agent.objects.get(user__username='djeneba.yirango')
            djenebaC = Agent.objects.get(user__username='djeneba.cisse')
            kani = Agent.objects.get(user__username='kani.traore')
            ramata = Agent.objects.get(user__username='ramata.sangare')
            sira = Agent.objects.get(user__username='sira.sidibe')
            noumoutene =  Agent.objects.get(user__username='noumoutene.toure')
            safiatou =  Agent.objects.get(user__username='safiatou.coulibaly')

            # 2. CONFIGURATION DES DISTRIBUTIONS MULTIPLES AVEC SPÉCIFICATIONS
            distributions_config = [

           
                 {
                    'date': '11/12/2025', 
                    'produit': 'oignon',
                    'lot_reference': '20251209-0001',
                    'specification': '',
                    'prix_gros': 10500,
                    'prix_detail': 11250,
                    
                    'distributions': [  
    
                       (koniba, 1, "Fatou"),  
                       (ramata, 1, "Fatou"),  
                       (abdoulaye, 1, "Fatou"),  
                       (mankoulako, 4, "Fatou"),  
                       
                       
                       ]
                },
                   {
                    'date': '12/12/2025', 
                    'produit': 'oignon',
                    'lot_reference': '20251209-0001',
                    'specification': '',
                    'prix_gros': 10500,
                    'prix_detail': 11250,
                    
                    'distributions': [  
    
                       (moussony, 3, "Fatou"),  
                       (noumoutene, 5, "Fatou"),  
                       (koniba, 3, "Fatou"),  
                       (ramata, 1, "Fatou"),  
                          (djenebaS, 2, "Fatou"),
                       
                       ]
                }
                 
           
                

                ]
            
            toutes_distributions = []
            
            for config in distributions_config:
                # Conversion de la date
                date_distribution = datetime.strptime(config['date'], '%d/%m/%Y')
                date_distribution = timezone.make_aware(date_distribution)
                
                print(f"\n{'='*60}")
                print(f"📅 DISTRIBUTION DU {config['date']}")
                print(f"📦 Produit: {config['produit']}")
                print(f"🔍 Spécification: {config['specification']}")
                print(f"💰 Prix gros: {config['prix_gros']} FCFA")
                print(f"💰 Prix détail: {config['prix_detail']} FCFA")
                print(f"{'='*60}")
                
                distributions_crees = []

                for agent, quantite, nom in config['distributions']:

                    print(f"\n🎯 Distribution à {nom}: {quantite} unités de {config['produit']}...")

                    # --- SELECTION DU LOT ---
                    if config.get('lot_reference'):
                        lot = LotEntrepot.objects.filter(
                            reference_lot=config['lot_reference'],
                            quantite_restante__gte=quantite
                        ).first()
                    else:
                        lot = LotEntrepot.objects.filter(
                            produit__nom=config['produit'],
                            quantite_restante__gte=quantite
                        ).order_by('date_reception').first()

                    if not lot:
                        print(f"❌ Aucun lot disponible ou quantité insuffisante pour {nom}")
                        continue

                    # --- CREATION DISTRIBUTION ---
                    est_retroactive = date_distribution.date() < timezone.now().date()

                    distrib = DistributionAgent.objects.create(
                        superviseur=superviseur,
                        agent_terrain=agent,
                        date_distribution=date_distribution,
                        est_retroactive=est_retroactive
                    )

                    # --- DETAIL DISTRIBUTION ---
                    detail = DetailDistribution.objects.create(
                        distribution=distrib,
                        lot=lot,
                        quantite=quantite,
                        prix_gros=config['prix_gros'],
                        prix_detail=config['prix_detail'],
                        specification=config['specification']
                    )

                    # --- MISE À JOUR STOCK ---
                    lot.quantite_restante -= quantite
                    lot.save()

                    # --- GENERATION DU MOUVEMENT STOCK ---
                    from core.models import MouvementStock

                    MouvementStock.objects.create(
                        type_mouvement="DISTRIBUTION",
                        produit=lot.produit,
                        lot=lot,
                        agent=agent,
                        quantite=quantite,
                        detail_distribution=detail,
                        date_mouvement=date_distribution
                    )

                    # --- MAJ TOTAUX ---
                    distrib._mettre_a_jour_totaux()

                    distributions_crees.append(distrib)

                    print(f"✅ Distribution OK (Lot : {lot.reference_lot}) - Stock restant : {lot.quantite_restante}")

                toutes_distributions.extend(distributions_crees)
                
                # Récapitulatif pour cette date
                total_date = sum(distrib.quantite_totale for distrib in distributions_crees)
                print(f"\n📊 RÉCAPITULATIF {config['date']}:")
                print(f"   📦 Distribué: {total_date} unités")
                print(f"   👥 Distributions: {len(distributions_crees)}")
                print(f"   🔍 Spécification: {config['specification']}")
            
            # 3. RÉCAPITULATIF GÉNÉRAL
            print("\n" + "="*60)
            print("🎉 TOUTES LES DISTRIBUTIONS TERMINÉES AVEC SUCCÈS!")
            print("="*60)
            
            # Statistiques par produit et spécification
            produits_specs_distribues = set()
            for distrib in toutes_distributions:
                for detail in distrib.detaildistribution_set.all():
                    spec = f"{detail.lot.produit.nom} ({detail.specification})"  # Utiliser specification du DetailDistribution
                    produits_specs_distribues.add(spec)
            
            print(f"\n📈 STATISTIQUES GÉNÉRALES:")
            print(f"📦 Total distributions créées: {len(toutes_distributions)}")
            print(f"🎯 Produits et spécifications distribués:")
            for produit_spec in produits_specs_distribues:
                print(f"   • {produit_spec}")
            
            # Détail par produit
            print(f"\n📊 STOCK RESTANT PAR PRODUIT:")
            produits_distribues = set()
            for distrib in toutes_distributions:
                for detail in distrib.detaildistribution_set.all():
                    produits_distribues.add(detail.lot.produit.nom)
            
            for produit in produits_distribues:
                stock_restant = LotEntrepot.objects.filter(
                    produit__nom=produit
                ).aggregate(total=models.Sum('quantite_restante'))['total'] or 0
                print(f"   • {produit}: {stock_restant} unités")
            
            # Détail des distributions créées
            print(f"\n👥 RÉCAPITULATIF DES DISTRIBUTIONS:")
            for distrib in toutes_distributions:
                detail = distrib.detaildistribution_set.first()
                produit_nom = detail.lot.produit.nom
                specification = detail.specification  # Récupérer la spécification du détail
                type_distrib = "🤖 Auto" if distrib.agent_terrain == superviseur else "👥 Terrain"
                retro = " 📅" if distrib.est_retroactive else ""
                
                print(f"   • {type_distrib} {distrib.agent_terrain.full_name}: "
                      f"{distrib.quantite_totale} {produit_nom} ({specification}) "
                      f"le {distrib.date_distribution.strftime('%d/%m/%Y')}{retro}")
                      
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

# Exécuter la fonction
creer_distributions_multiple()