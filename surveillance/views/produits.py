from django.shortcuts import (
    get_object_or_404
)

from django.views.generic import (
    TemplateView
)

from core.models import Produit

from surveillance.services.detail_produit_service import (
    DetailProduitService
)


class DetailProduitView(
    TemplateView
):

    template_name = (
        "surveillance/produits/detail_produit.html"
    )

    def get_context_data(
        self,
        **kwargs
    ):

        context = super().get_context_data(
            **kwargs
        )

        produit = get_object_or_404(
            Produit,
            pk=self.kwargs["pk"]
        )

        context.update(
            DetailProduitService
            .get_data(
                produit
            )
        )

        return context