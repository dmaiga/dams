from django.core.management.base import BaseCommand
from core.models import LotEntrepot


class Command(BaseCommand):
    help = "Normalise les quantités des lots en kilogrammes (migration métier)"

    CONVERSION_FACTORS = {
        "ail": 10,
        "oignon": 25,
        "pomme de terre": 25,
    }

    def handle(self, *args, **options):
        lots = LotEntrepot.objects.select_related("produit").all()

        self.stdout.write(self.style.WARNING(
            f"🔎 {lots.count()} lots trouvés"
        ))

        for lot in lots:
            produit_nom = lot.produit.nom.lower().strip()
            facteur = self.CONVERSION_FACTORS.get(produit_nom, 1)

            ancienne_init = lot.quantite_initiale
            ancienne_rest = lot.quantite_restante

            # Conversion vers kg
            lot.quantite_initiale = ancienne_init * facteur
            lot.quantite_restante = ancienne_rest * facteur
            lot.valeur_stock_initiale = (
                lot.quantite_initiale * lot.prix_achat_unitaire
            )

            lot.save(update_fields=[
                "quantite_initiale",
                "quantite_restante",
                "valeur_stock_initiale"
            ])

            self.stdout.write(
                f"✅ Lot {lot.id} | {lot.produit.nom} | "
                f"{ancienne_init} → {lot.quantite_initiale} kg | "
                f"reste {ancienne_rest} → {lot.quantite_restante} kg"
            )

        self.stdout.write(self.style.SUCCESS(
            "🎉 Migration terminée avec succès"
        ))
