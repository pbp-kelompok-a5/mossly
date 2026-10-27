from django.urls import path
from . import views

app_name = "carbon"
urlpatterns = [
    # CRUD
    path("", views.index, name="index"),
    path("add/", views.trip_form, name="add_trip"),
    path("edit/<int:pk>/", views.trip_form, name="edit_trip"),
    path("delete/<int:pk>/", views.delete_trip, name="delete_trip"),

    # API endpoints
    path("api/geocode/", views.api_geocode, name="api_geocode"),
    path("api/reverse/", views.api_reverse_geocode, name="api_reverse_geocode"),
    path("api/route/", views.api_route, name="api_route"),
    path("api/history/", views.api_history, name="api_history"),
]
