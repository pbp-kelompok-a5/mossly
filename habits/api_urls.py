"""Endpoint DRF modul Sustainable Habit & Goal Tracker. Terpasang di /api/v1/habits/ dan goals/"""
from django.urls import path

from . import api_views

app_name = "habits_api"
urlpatterns = [
    path("habits/", api_views.habit_list, name="habit-list"),
]
