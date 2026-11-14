from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # Web service Django REST Framework untuk aplikasi mobile.
    path("api/v1/", include("mossly.api_urls")),
    # Login/logout untuk halaman uji DRF di browser (Browsable API), seperti Tutorial 07.
    path("api-auth/", include("rest_framework.urls")),
    path("", include("main.urls")),
    path("accounts/", include("accounts.urls")),
    path("carbon/", include("carbon.urls")),
    # Habit & Goal pages live under /habit/ and /goal/ (prefixes set in the app).
    path("", include("habits.urls")),
    path("community/", include("community.urls")),
    path("dashboard/", include("dashboard.urls")),
]