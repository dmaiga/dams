# management/commands/reception_ail.py
#  python manage.py reception_ail --quantite 50 --date 01/09/2025 --prix 9500
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime
from core.models import LotEntrepot, Produit, Fournisseur

class Command(BaseCommand):
    help = 'Crée une réception d\'ail avec fournisseur inconnu'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quantite',
            type=int,
            required=True,
            help='Quantité initiale du lot'
        )
        parser.add_argument(
            '--date',
            type=str,
            required=True,
            help='Date de réception (format: DD/MM/YYYY)'
        )
        parser.add_argument(
            '--prix',
            type=float,
            required=True,
            help='Prix d\'achat unitaire'
        )
        parser.add_argument(
            '--produit',
            type=str,
            default='ail',
            help='Nom du produit (défaut: ail)'
        )

    def handle(self, *args, **options):
        
        try:
            # Paramètres de réception
            produit_nom = options['produit']
            prix_achat_unitaire = options['prix']
            quantite = options['quantite']
            date_reception_str = options['date']
            
            # Conversion de la date
            date_reception = datetime.strptime(date_reception_str, '%d/%m/%Y')
            
            self.stdout.write("🚀 DÉBUT DE LA RÉCEPTION...")
            self.stdout.write(f"📦 Produit: {produit_nom}")
            self.stdout.write(f"💰 Prix d'achat: {prix_achat_unitaire} FCFA")
            self.stdout.write(f"📊 Quantité: {quantite} unités")
            self.stdout.write(f"📅 Date réception: {date_reception}")
            
            # 1. VÉRIFICATION DU PRODUIT
            self.stdout.write("\n🔍 Vérification du produit...")
            try:
                produit = Produit.objects.get(nom=produit_nom)
                self.stdout.write(self.style.SUCCESS(f"✅ Produit trouvé: {produit.nom}"))
            except Produit.DoesNotExist:
                self.stdout.write(self.style.WARNING("❌ Produit non trouvé, création..."))
                produit = Produit.objects.create(nom=produit_nom)
                self.stdout.write(self.style.SUCCESS(f"✅ Nouveau produit créé: {produit.nom}"))

            # 2. CRÉATION DU LOT
            self.stdout.write("\n📝 Création du lot...")
            
            # Génération référence lot
            reference_lot = f"{produit_nom.upper()}_{date_reception.strftime('%Y%m%d')}_{int(timezone.now().timestamp())}"
            
            lot = LotEntrepot.objects.create(
                produit=produit,
                fournisseur=None,  # Fournisseur inconnu
                quantite_initiale=quantite,
                quantite_restante=quantite,
                prix_achat_unitaire=prix_achat_unitaire,
                date_reception=date_reception,  # Date rétroactive
                reference_lot=reference_lot,
                facture=None,
                date_upload_facture=None
            )
            
            self.stdout.write(self.style.SUCCESS(f"✅ Lot créé avec référence: {reference_lot}"))
            
            # 3. AFFICHAGE DU RÉCAPITULATIF
            self.stdout.write("\n" + "="*50)
            self.stdout.write(self.style.SUCCESS("📋 RÉCEPTION TERMINÉE AVEC SUCCÈS!"))
            self.stdout.write("="*50)
            self.stdout.write(f"🎯 Référence lot: {lot.reference_lot}")
            self.stdout.write(f"📦 Produit: {lot.produit.nom}")
            self.stdout.write(f"📊 Quantité: {lot.quantite_initiale} unités")
            self.stdout.write(f"💰 Prix unitaire: {lot.prix_achat_unitaire} FCFA")
            self.stdout.write(f"💵 Montant total: {lot.montant_total} FCFA")
            self.stdout.write(f"📅 Date réception: {lot.date_reception}")
            self.stdout.write(f"👤 Fournisseur: {'Inconnu' if not lot.fournisseur else lot.fournisseur.nom}")
            self.stdout.write(f"📄 Facture: {'Non fournie' if not lot.facture else 'Fournie'}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la réception: {e}"))