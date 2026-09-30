from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("accounts/", include("accounts.urls")),
    path("carbon/", include("carbon.urls")),
    path("habits/", include("habits.urls")),
    path("community/", include("community.urls")),
    path("dashboard/", include("dashboard.urls")),
]