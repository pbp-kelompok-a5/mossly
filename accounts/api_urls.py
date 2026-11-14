"""Endpoint DRF modul Login & Onboarding. Terpasang di /api/v1/auth/

File ini masih kosong, silakan mulai menambahkan route endpoint modul di urlpatterns di bawah.
"""
from django.urls import path

from . import api_views  # noqa: F401

app_name = "accounts_api"
urlpatterns = [
    # path("contoh/", api_views.contoh_list, name="contoh-list"),
]
