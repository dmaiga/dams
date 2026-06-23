from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from core.models import LotEntrepot
from surveillance.mixins import SurveillanceAccessMixin
from surveillance.services.surveillance_prix_service import SurveillancePrixService


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

        return context