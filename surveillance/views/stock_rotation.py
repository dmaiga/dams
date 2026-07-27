from django.core.paginator import Paginator
from django.views.generic import TemplateView

from surveillance.mixins import SurveillanceAccessMixin
from surveillance.services.stock_age_service import StockAgeService

TAILLE_PAGE = 20


class StockRotationView(SurveillanceAccessMixin, TemplateView):
    """Pas de filtre semaine : les fenêtres glissantes (2j / 14j) se calculent
    depuis timezone.now(), pas depuis une semaine calendaire sélectionnée."""
    template_name = "surveillance/stock_rotation/dashboard_stock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            "theme": "stock",
            "qs_semaine": "",
            "agents_sans_vente": StockAgeService.agents_sans_vente_recente(limit=10),
            "nb_agents_sans_vente": StockAgeService.count_agents_sans_vente_recente(),
            "lots_dormants": StockAgeService.lots_stock_dormant(limit=10),
            "nb_lots_dormants": StockAgeService.count_lots_stock_dormant(),
            "valeur_stock_dormant": StockAgeService.valeur_stock_dormant(),
        })

        return context


class RotationLenteListView(SurveillanceAccessMixin, TemplateView):
    """Liste complète (sans limite) des agents en rotation lente."""
    template_name = "surveillance/stock_rotation/liste_rotation_lente.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        paginator = Paginator(StockAgeService.agents_sans_vente_recente(), TAILLE_PAGE)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        context.update({
            "theme": "stock",
            "qs_semaine": "",
            "agents_sans_vente": page_obj,
            "page_obj": page_obj,
            "nb_agents_sans_vente": StockAgeService.count_agents_sans_vente_recente(),
        })

        return context


class StockDormantListView(SurveillanceAccessMixin, TemplateView):
    """Liste complète (sans limite) des lots en stock dormant."""
    template_name = "surveillance/stock_rotation/liste_stock_dormant.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        paginator = Paginator(StockAgeService.lots_stock_dormant(), TAILLE_PAGE)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        context.update({
            "theme": "stock",
            "qs_semaine": "",
            "lots_dormants": page_obj,
            "page_obj": page_obj,
            "nb_lots_dormants": StockAgeService.count_lots_stock_dormant(),
            "valeur_stock_dormant": StockAgeService.valeur_stock_dormant(),
        })

        return context
