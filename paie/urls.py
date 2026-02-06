from django.urls import path


from paie.views import (
                         SalaireLectureView,SalaireGenerationView,
                         SalaireValidationView,export_salaires_mamies_excel,
                         export_salaires_gros_excel
                        )
from paie import views 

urlpatterns = [
        path('direction/paie/', SalaireLectureView.as_view(), name='salaire_lecture'),
        path('direction/paie/generation', SalaireGenerationView.as_view(), name='salaire_generation'),
        path("direction/paie/validation",SalaireValidationView.as_view(),name="salaire_validation"),
        path(
            "salaires/mamies/export-excel/",
            export_salaires_mamies_excel,
            name="export_salaires_mamies_excel"
        ),
        path(
            "salaires/agent-gros/export-excel/",
            export_salaires_gros_excel,
            name="export_salaires_gros_excel"
        ),        
        ]