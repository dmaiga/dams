from django.db.models import Sum, Count, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from core.models import Vente,Agent



class RapportVentesService:
    @staticmethod
    def rapport_agents(date_debut, date_fin):

        ventes = (
            Vente.objects
            .filter(
                date_vente__date__range=(date_debut, date_fin),
                agent__est_actif=True,
                est_supprime=False
            )
            .values(
                "agent__id",
                "agent__user__first_name",
                "agent__user__last_name",
                "date_vente__date",
                "detail_distribution__lot__produit__nom",
                "detail_distribution__lot__produit__poids_unitaire_kg"
            )
            .annotate(
                # 🔹 Quantité vendue (unités)
                total_quantite=Sum("quantite"),

                # 🔹 Nombre de ventes
                nombre_ventes=Count("id"),

                # 🔹 CA officiel
                total_ca=Sum(
                    F("quantite") * F("prix_vente_unitaire"),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),

                # 🆕 POIDS TOTAL VENDU (KG)
                total_kg=Sum(
                    F("quantite") *
                    Coalesce(
                        F("detail_distribution__lot__produit__poids_unitaire_kg"),
                        Decimal("1")
                    ),
                    output_field=DecimalField(max_digits=15, decimal_places=2)
                ),
            )
            .order_by(
                "agent__user__last_name",
                "date_vente__date",
                "detail_distribution__lot__produit__nom",
            )
        )

        return ventes

    @staticmethod
    def agents_sans_vente(date_debut, date_fin):

        # Agents ayant vendu sur la période
        agents_ayant_vendu = (
            Vente.objects
            .filter(
                date_vente__date__range=(date_debut, date_fin),
                est_supprime=False
            )
            .values_list("agent_id", flat=True)
            .distinct()
        )

        # ✅ uniquement agents commerciaux
        agents_sans_vente = (
            Agent.objects
            .filter(
                est_actif=True,
                type_agent__in=['terrain', 'agent_gros','stagiaire','agent_polivalent']
            )
            .exclude(id__in=agents_ayant_vendu)
            .select_related("user")
            .order_by("user__last_name")
        )

        return agents_sans_vente
