from django.shortcuts import render
from . import selectors, services


# =======================================
# 1. KPIs Direction
# =======================================
def kpis(request):
    kpi_data = services.compute_kpis()

    return render(
        request,
        "direction/partials/kpis.html",
        {"kpis": kpi_data},
    )


# =======================================
# 2. STOCK
# =======================================
def stock(request):
    stock_global = selectors.get_stock_global()
    lots = selectors.get_lots_details()

    return render(
        request,
        "direction/partials/table_stock.html",
        {
            "stock_global": stock_global,
            "lots": lots,
        }
    )


# =======================================
# 3. VENTES
# =======================================
def ventes(request):
    ventes = selectors.get_ventes_direction()

    return render(
        request,
        "direction/partials/table_ventes.html",
        {
            "ventes": ventes,
        }
    )


# =======================================
# 4. AGENTS / SUPERVISEURS
# =======================================
def agents(request):
    agents = selectors.get_agents_performance()

    return render(
        request,
        "direction/partials/table_agents.html",
        {"agents": agents},
    )


# =======================================
# 5. DETTES / RECOUVREMENTS
# =======================================
def dettes(request):
    dettes = selectors.get_dettes_direction()

    return render(
        request,
        "direction/partials/table_dettes.html",
        {"dettes": dettes},
    )


# =======================================
# 6. DÉPENSES
# =======================================
def depenses(request):
    depenses = selectors.get_depenses_direction()

    return render(
        request,
        "direction/partials/table_depenses.html",
        {"depenses": depenses},
    )
