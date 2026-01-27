from django.core.management.base import BaseCommand
from core.models import Produit
from decimal import Decimal

class Command(BaseCommand):
    help = "Initialise les poids unitaires des produits"

    def handle(self, *args, **options):
        mapping = {
            "ail": Decimal("10"),
            "oignon": Decimal("25"),
            "pomme de terre": Decimal("25"),
        }

        updated = 0
        for nom, poids in mapping.items():
            qs = Produit.objects.filter(nom__iexact=nom)
            updated += qs.update(poids_unitaire_kg=poids)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Poids unitaires mis à jour ({updated} produits)"
        ))
