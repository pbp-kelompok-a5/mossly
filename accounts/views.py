from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import logout


def login_view(request):
    return render(request, "accounts/login.html", {
        "preview_submitted": request.method == "POST",
    })


def register_view(request):
    return HttpResponse("Placeholder register")


def logout_view(request):
    logout(request)
    return redirect("main:landing")
