"""Endpoint baca Community; autentikasi mengikuti konfigurasi DRF bersama."""

from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .serializers import ThreadFeedQuerySerializer, ThreadSerializer
from .views import threads_for


@never_cache
@api_view(["GET"])
def thread_list(request):
    """Feed bersama, dengan status like sesuai pengguna yang sedang login."""
    query = ThreadFeedQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    threads = threads_for(request.user)
    if filters["category"]:
        threads = threads.filter(category=filters["category"])
    if filters["author"]:
        threads = threads.filter(author__username__icontains=filters["author"])

    paginator = Paginator(threads, 8)
    try:
        page = paginator.page(filters["page"])
    except EmptyPage:
        raise NotFound("Halaman tidak ditemukan.")

    return Response({
        "category": filters["category"],
        "results": ThreadSerializer(page.object_list, many=True).data,
        "pagination": {
            "page": page.number,
            "total_pages": paginator.num_pages,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        },
    })


@never_cache
@api_view(["GET"])
def thread_detail(request, pk):
    """Pengguna yang login dapat membaca thread siapa pun di Community."""
    thread = get_object_or_404(threads_for(request.user), pk=pk)
    return Response(ThreadSerializer(thread).data)
