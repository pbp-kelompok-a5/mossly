from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth import logout


def login_view(request):
    return HttpResponse("Placeholder login")


def register_view(request):
    return HttpResponse("Placeholder register")


def logout_view(request):
    logout(request)
    return redirect("main:landing")