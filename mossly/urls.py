from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls")),
    path("accounts/", include("accounts.urls")),
    path("carbon/", include("carbon.urls")),
    # Habit & Goal pages live under /habit/ and /goal/ (prefixes set in the app).
    path("", include("habits.urls")),
    path("community/", include("community.urls")),
    path("dashboard/", include("dashboard.urls")),
]