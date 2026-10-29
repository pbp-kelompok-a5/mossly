from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("badges/", views.badges, name="badges"),
    path("target/", views.targets, name="targets"),
    path("target/baru/", views.target_create, name="target_create"),
    path("target/<int:pk>/ubah/", views.target_edit, name="target_edit"),
    path("target/<int:pk>/hapus/", views.target_delete, name="target_delete"),
    path("api/summary/", views.api_summary, name="api_summary"),
]