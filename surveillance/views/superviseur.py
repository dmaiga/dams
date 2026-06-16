from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from core.models import Agent

from surveillance.services.detail_superviseur_service import (
    DetailSuperviseurService
)


class DetailSuperviseurView(
    TemplateView
):

    template_name = (
        "surveillance/superviseur/detail_superviseur.html"
    )

    def get_context_data(
        self,
        **kwargs
    ):

        context = super().get_context_data(
            **kwargs
        )

        superviseur = get_object_or_404(
            Agent,
            pk=self.kwargs["pk"]
        )

        context.update(
            DetailSuperviseurService
            .get_data(
                superviseur
            )
        )

        return context