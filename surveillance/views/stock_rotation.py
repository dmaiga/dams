from django.core.paginator import Paginator
from django.views.generic import TemplateView

from surveillance.mixins import SurveillanceAccessMixin
from surveillance.services.stock_age_service import StockAgeService

TAILLE_PAGE = 20


class StockRotationView(SurveillanceAccessMixin, TemplateView):
    """Stock dormant à l'entrepôt central uniquement (non distribué depuis
    plus de 15 jours). Le suivi de rétention chez les superviseurs/agents et
    de l'activité commerciale des agents est couvert ailleurs avec plus de
    précision (`direction.suivi_distributions`, filtrable par agent/
    superviseur/produit/période) — pas de redondance ici. Pas de filtre
    semaine : la fenêtre glissante se calcule depuis timezone.now()."""
    template_name = "surveillance/stock_rotation/dashboard_stock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            "theme": "stock",
            "qs_semaine": "",
            "lots_dormants": StockAgeService.lots_dormants_entrepot(limit=10),
            "nb_lots_dormants": StockAgeService.count_lots_dormants_entrepot(),
            "valeur_stock_dormant": StockAgeService.valeur_stock_dormant_entrepot(),
        })

        return context


class StockDormantListView(SurveillanceAccessMixin, TemplateView):
    """Liste complète (sans limite) des lots en stock dormant à l'entrepôt."""
    template_name = "surveillance/stock_rotation/liste_stock_dormant.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        paginator = Paginator(StockAgeService.lots_dormants_entrepot(), TAILLE_PAGE)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        context.update({
            "theme": "stock",
            "qs_semaine": "",
            "lots_dormants": page_obj,
            "page_obj": page_obj,
            "nb_lots_dormants": StockAgeService.count_lots_dormants_entrepot(),
            "valeur_stock_dormant": StockAgeService.valeur_stock_dormant_entrepot(),
        })

        return context
