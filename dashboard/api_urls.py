"""Endpoint DRF modul Personal Sustainability Dashboard. Terpasang di /api/v1/dashboard/

File ini masih kosong, silakan mulai menambahkan route endpoint modul di urlpatterns di bawah.
"""
from django.urls import path

from . import api_views  # noqa: F401

app_name = "dashboard_api"
urlpatterns = [
    # path("contoh/", api_views.contoh_list, name="contoh-list"),
]
