from django.urls import path
from . import views

app_name = "carbon"
urlpatterns = [path("", views.index, name="index")]