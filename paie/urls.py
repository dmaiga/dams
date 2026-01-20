from django.urls import path


from paie.views import SalaireLectureView,SalaireGenerationView, SalaireValidationView
from paie import views 

urlpatterns = [
        path('direction/paie/', SalaireLectureView.as_view(), name='salaire_lecture'),
        path('direction/paie/generation', SalaireGenerationView.as_view(), name='salaire_generation'),
       path("direction/paie/validation",SalaireValidationView.as_view(),name="salaire_validation"),

        ]