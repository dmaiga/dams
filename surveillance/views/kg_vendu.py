from django.views.generic import TemplateView

from core.models import Produit, Agent

from surveillance.services.liste_kg_service import (
    ListeKgVenduService
)

from surveillance.services.comparaison_service import (
    ComparaisonPeriodeService
)


class ListeKgVenduView(TemplateView):

    template_name = (
        "surveillance/kg_vendu/liste_kg_vendu.html"
    )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        periode = self.request.GET.get(
            "periode",
            "semaine"
        )


        superviseur = self.request.GET.get(
            "superviseur"
        )

        produit = self.request.GET.get(
            "produit"
        )
        superviseur = (
            int(superviseur)
            if superviseur
            else None
        )
        
        produit = (
            int(produit)
            if produit
            else None
        )
        # ------------------
        # Période
        # ------------------

        if periode == "mois":

            date_debut, date_fin = (
                ComparaisonPeriodeService
                .mois_actuel()
            )

        else:

            date_debut, date_fin = (
                ComparaisonPeriodeService
                .semaine_actuelle()
            )

        # ------------------
        # Données
        # ------------------

        kpis = (
            ListeKgVenduService.get_kpis(
                date_debut,
                date_fin
            )
        )

        superviseurs_stats = (
            ListeKgVenduService.get_superviseurs(
                date_debut,
                date_fin
            )
        )

        agents_stats = (
            ListeKgVenduService.get_agents(
                date_debut,
                date_fin,
                superviseur=superviseur,
                produit=produit
            )
        )

        context.update({

            "periode": periode,

            "kpis": kpis,

            "superviseurs_stats":
                superviseurs_stats,

            "agents_stats":
                agents_stats,

            "superviseurs":
                Agent.objects.filter(
                    type_agent="entrepot",
                    est_actif=True
                ),

            "produits":
                Produit.objects.all(),

            "selected_superviseur":
                superviseur,

            "selected_produit":
                produit,
        })

        return context