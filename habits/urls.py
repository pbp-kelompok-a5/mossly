from django.urls import path
from . import views

app_name = "habits"
urlpatterns = [
    path("habit/", views.index, name="index"),
    path("habit/new/", views.habit_create, name="habit_create"),
    path("api/habits/", views.habits_json, name="habits_json"),
    path("habit/history/", views.history, name="history"),
    path("habit/<int:pk>/", views.habit_detail, name="habit_detail"),
    path("habit/<int:pk>/edit/", views.habit_edit, name="habit_edit"),
    path("habit/<int:pk>/delete/", views.habit_delete, name="habit_delete"),
    path("habit/<int:pk>/check-in/", views.habit_check_in, name="habit_check_in"),
    path("habit/<int:pk>/undo/", views.habit_undo_check_in, name="habit_undo_check_in"),
    path("goal/", views.goal_list, name="goal_list"),
    path("goal/new/", views.goal_create, name="goal_create"),
    path("api/goals/", views.goals_json, name="goals_json"),
    path("goal/<int:pk>/", views.goal_detail, name="goal_detail"),
    path("goal/<int:pk>/edit/", views.goal_edit, name="goal_edit"),
    path("goal/<int:pk>/progress/", views.goal_log_progress, name="goal_log_progress"),
    path("goal/<int:pk>/delete/", views.goal_delete, name="goal_delete"),
    path(
        "goal/<int:pk>/checklist/<int:item_pk>/toggle/",
        views.goal_checklist_toggle,
        name="goal_checklist_toggle",
    ),
]
