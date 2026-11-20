from django.urls import path

from . import api_views

app_name = 'carbon_api'

urlpatterns = [
    path('modes/', api_views.mode_list, name='mode-list'),
    path('trips/', api_views.trip_list, name='trip-list'),
]
