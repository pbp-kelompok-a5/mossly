from urllib.parse import urlsplit

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .forms import LoginForm


class AccountsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_redirect_url(self):
        # LoginView sudah menolak host asing. Hindari juga putaran redirect
        # ke halaman autentikasi sendiri lewat parameter next.
        target = super().get_redirect_url()
        auth_paths = {
            reverse("accounts:login"),
            reverse("accounts:register"),
            reverse("accounts:logout"),
        }
        if urlsplit(target).path.rstrip("/") in {
            path.rstrip("/") for path in auth_paths
        }:
            return ""
        return target


login_view = AccountsLoginView.as_view()


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    return HttpResponse("Placeholder register")


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("main:landing")
    return render(request, "accounts/logout.html")
