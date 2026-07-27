from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from core.models import LotEntrepot
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.services.surveillance_prix_service import SurveillancePrixService
from surveillance.week_utils import qs_semaine


class SurveillancePrixView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/prix/surveillance_prix.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Tri des anomalies de prix par date de réception
        order = self.request.GET.get("order", "-date_reception")

        context.update(
            SurveillancePrixService.get_resume(order_by=order)
        )
        context["current_order"] = order

        # Pas de filtre semaine propre à cette vue : on ne fait que reporter
        # celui éventuellement porté par le lien entrant, pour la nav commune.
        semaine_selectionnee = self.request.GET.get("semaine", "")
        context["theme"] = "prix"
        context["semaine_selectionnee"] = semaine_selectionnee
        context["qs_semaine"] = qs_semaine(semaine_selectionnee)

        return context


class DetailPrixView(SurveillanceAccessMixin, TemplateView):
    template_name = "surveillance/prix/detail_prix.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        lot = get_object_or_404(
            LotEntrepot,
            pk=self.kwargs["lot_id"]
        )

        context.update(
            SurveillancePrixService.get_detail_lot(lot)
        )

        context["theme"] = "prix"
        context["qs_semaine"] = ""

        return context