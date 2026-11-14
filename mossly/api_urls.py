"""Pintu masuk web service (Django REST Framework) untuk aplikasi mobile.

Semua endpoint berada di bawah /api/v1/. Setiap modul mengisi api_urls.py
di app-nya sendiri; file ini tidak perlu diubah lagi.
"""
from django.urls import include, path

from . import api_views

urlpatterns = [
    path("ping/", api_views.ping, name="api_ping"),
    path("auth/", include("accounts.api_urls")),         # Login & Onboarding
    path("carbon/", include("carbon.api_urls")),         # Carbon Footprint Tracker
    path("", include("habits.api_urls")),                # habits/ dan goals/
    path("community/", include("community.api_urls")),   # Sustainability Community
    path("dashboard/", include("dashboard.api_urls")),   # Personal Sustainability Dashboard
]
