from django.urls import path
from . import views

urlpatterns = [
    path("", views.mobile_login, name="mobile_login"),
    path("home/", views.mobile_home, name="mobile_home"),
]
