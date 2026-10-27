from django.urls import path
from . import views

app_name = "habits"
urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/check-in/", views.habit_check_in, name="habit_check_in"),
    path("<int:pk>/undo/", views.habit_undo_check_in, name="habit_undo_check_in"),
    path("<int:pk>/delete/", views.habit_delete, name="habit_delete"),
    path("goals/<int:pk>/progress/", views.goal_log_progress, name="goal_log_progress"),
    path("goals/<int:pk>/delete/", views.goal_delete, name="goal_delete"),
]
