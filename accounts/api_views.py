"""Register, login, logout, dan profil untuk klien Flutter berbasis token."""
from django.db import IntegrityError, transaction
from django.views.decorators.cache import never_cache
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import CurrentUserSerializer, LoginSerializer, RegisterSerializer
from .views import get_profile


def current_user_data(user):
    return CurrentUserSerializer(get_profile(user)).data


@never_cache
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        # User, profil, dan token harus berhasil bersama. Kegagalan token tidak
        # boleh meninggalkan akun setengah jadi yang tidak bisa didaftarkan ulang.
        with transaction.atomic():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            data = {"token": token.key, "user": current_user_data(user)}
    except IntegrityError:
        raise serializers.ValidationError({
            "non_field_errors": [
                "Akun tidak dapat dibuat. Periksa username dan coba lagi."
            ],
        })
    return Response(data, status=status.HTTP_201_CREATED)


@never_cache
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": current_user_data(user)})


@never_cache
@api_view(["POST"])
def logout(request):
    # Default permission IsAuthenticated melindungi endpoint ini. Hanya token
    # akun aktif yang dicabut; session website dan akun orang lain tetap utuh.
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@never_cache
@api_view(["GET"])
def me(request):
    return Response(current_user_data(request.user))
