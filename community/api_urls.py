"""Endpoint DRF Community di /api/v1/community/."""
from django.urls import path

from . import api_views

app_name = "community_api"
urlpatterns = [
    path("threads/", api_views.thread_list, name="thread-list"),
    path("threads/<int:pk>/", api_views.thread_detail, name="thread-detail"),
]
