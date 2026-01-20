from django.urls import path


from paie.views import SalaireLectureView
from paie import views 

urlpatterns = [
        path('direction/paie/', SalaireLectureView.as_view(), name='salaire_lecture'),
        ]