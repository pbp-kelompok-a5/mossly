from django.urls import path
from . import views

app_name = "community"
urlpatterns = [
    path("", views.index, name="index"),
    path("threads.json/", views.threads_json, name="threads_json"),
    path("new/", views.thread_form, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.thread_form, name="edit"),
    path("<int:pk>/delete/", views.delete, name="delete"),
    path("<int:pk>/like/", views.like, name="like"),
]
