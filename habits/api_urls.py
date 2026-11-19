"""Endpoint DRF modul Sustainable Habit & Goal Tracker. Terpasang di /api/v1/habits/ dan /api/v1/goals/"""
from django.urls import path
from . import api_views

app_name = "habits_api"
urlpatterns = [
    path("habits/", api_views.habit_list, name="habit-list"),
    path("goals/", api_views.goal_list, name="goal-list"),
]
