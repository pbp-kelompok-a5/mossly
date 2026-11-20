from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .models import Achievement
from .serializers import BadgeSerializer


@api_view(["GET"])
def summary(request):
    return Response(services.api_summary(request.user, timezone.localdate()))


@api_view(["GET"])
def badges(request):
    today = timezone.localdate()
    metrics, _ = services.check_and_award(request.user, today)
    rows = services.badge_rows(request.user, metrics)
    kategori = request.query_params.get("kategori")
    if kategori:
        if kategori not in Achievement.Category.values:
            return Response(
                {"kategori": ["Kategori tidak dikenal."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = [r for r in rows if r["category"] == kategori]
    return Response(
        {
            "earned": sum(1 for r in rows if r["earned"]),
            "total": len(rows),
            "badges": BadgeSerializer(rows, many=True).data,
        }
    )