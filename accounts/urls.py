from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("onboarding/", views.onboarding_view, name="onboarding"),
    path("profile/", views.profile_view, name="profile"),
    path("check-username/", views.check_username, name="check_username"),
    path("me/json/", views.current_user_json, name="current_user_json"),
    path("delete/", views.delete_account, name="delete"),
]
