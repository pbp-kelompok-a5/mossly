"""Endpoint DRF modul Sustainable Habit & Goal Tracker. Terpasang di /api/v1/habits/ dan goals/

File ini masih kosong, silakan mulai menambahkan route endpoint modul di urlpatterns di bawah.
"""
from django.urls import path

from . import api_views  # noqa: F401

app_name = "habits_api"
urlpatterns = [
    # path("contoh/", api_views.contoh_list, name="contoh-list"),
]
