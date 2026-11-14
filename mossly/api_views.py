from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def ping(request):
    """Cek cepat: server hidup, dan token yang dikirim dikenali atau tidak."""
    user = request.user
    return Response({
        "status": "ok",
        "app": "mossly",
        "authenticated": user.is_authenticated,
        "username": user.get_username() if user.is_authenticated else None,
    })
