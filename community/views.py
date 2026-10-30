from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ReplyForm, ThreadForm
from .models import Reply, Thread, ThreadLike


def is_async_request(request):
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


def threads_for(user):
    like_count = (
        ThreadLike.objects.filter(thread_id=OuterRef("pk"))
        .order_by()
        .values("thread_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )
    reply_count = (
        Reply.objects.filter(thread_id=OuterRef("pk"))
        .order_by()
        .values("thread_id")
        .annotate(total=Count("pk"))
        .values("total")[:1]
    )

    return (
        Thread.objects.select_related(
            "author",
            "author__profile",
            "user_achievement",
        )
        .annotate(
            like_count=Coalesce(
                Subquery(like_count, output_field=IntegerField()),
                Value(0),
            ),
            reply_count=Coalesce(
                Subquery(reply_count, output_field=IntegerField()),
                Value(0),
            ),
            is_liked=Exists(
                ThreadLike.objects.filter(
                    thread_id=OuterRef("pk"),
                    user=user,
                )
            ),
        )
        .order_by("-created_at", "pk")
    )


@login_required
def index(request):
    category = request.GET.get("category", "")
    author = request.GET.get("author", "").strip()
    threads = threads_for(request.user)

    if category in Thread.Category.values:
        threads = threads.filter(category=category)
    else:
        category = ""

    if author:
        threads = threads.filter(author__username__icontains=author)

    context = {
        "page_obj": Paginator(threads, 8).get_page(request.GET.get("page")),
        "category": category,
        "thread_total": Thread.objects.count(),
        "member_total": Thread.objects.values("author").distinct().count(),
        "achievement_total": Thread.objects.filter(
            category=Thread.Category.ACHIEVEMENT
        ).count(),
    }

    if is_async_request(request):
        return JsonResponse(
            {
                "thread_html": render_to_string(
                    "community/thread_feed.html",
                    context,
                    request=request,
                ),
                "category": category,
            }
        )

    return render(request, "community/index.html", context)


@login_required
def threads_json(request):
    category = request.GET.get("category", "")
    author = request.GET.get("author", "").strip()
    threads = threads_for(request.user)

    if category in Thread.Category.values:
        threads = threads.filter(category=category)
    else:
        category = ""

    if author:
        threads = threads.filter(author__username__icontains=author)

    page_obj = Paginator(threads, 8).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "category": category,
            "results": [
                {
                    "id": thread.pk,
                    "title": thread.title,
                    "body": thread.body,
                    "category": thread.category,
                    "created_at": thread.created_at.isoformat(),
                    "author": {
                        "username": thread.author.username,
                        "display_name": thread.author.profile.display_name
                        or thread.author.username,
                        "avatar": thread.author.profile.avatar,
                    },
                    "like_count": thread.like_count,
                    "reply_count": thread.reply_count,
                    "is_liked": thread.is_liked,
                    "detail_url": reverse("community:detail", args=[thread.pk]),
                }
                for thread in page_obj
            ],
            "pagination": {
                "page": page_obj.number,
                "total_pages": page_obj.paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }
    )


@login_required
def detail(request, pk):
    thread = get_object_or_404(threads_for(request.user), pk=pk)
    form = ReplyForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            reply = form.save(commit=False)
            reply.author = request.user
            reply.thread = thread
            reply.save()

            if is_async_request(request):
                return JsonResponse(
                    {
                        "reply_html": render_to_string(
                            "community/reply_item.html",
                            {"reply": reply},
                            request=request,
                        ),
                        "reply_count": thread.replies.count(),
                        "message": "Balasanmu sudah ikut menumbuhkan obrolan. Terima kasih!",
                    }
                )

            messages.success(
                request,
                "Balasanmu sudah ikut menumbuhkan obrolan. Terima kasih!",
            )
            return redirect("community:detail", pk=pk)

        if is_async_request(request):
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    return render(
        request,
        "community/detail.html",
        {
            "thread": thread,
            "form": form,
            "replies": thread.replies.select_related("author", "author__profile").order_by(
                "created_at", "pk"
            ),
        },
    )


@login_required
def thread_form(request, pk=None):
    thread = (
        get_object_or_404(
            Thread,
            pk=pk,
            author=request.user,
            is_auto_post=False,
        )
        if pk
        else None
    )
    form = ThreadForm(request.POST or None, instance=thread)

    if request.method == "POST" and form.is_valid():
        thread = form.save(commit=False)
        thread.author = request.user
        thread.save()
        messages.success(
            request,
            "Cerita berhasil disimpan. Satu cerita, banyak inspirasi!",
        )
        return redirect("community:detail", pk=thread.pk)

    return render(
        request,
        "community/form.html",
        {"form": form, "thread": thread},
    )


@login_required
def delete(request, pk):
    thread = get_object_or_404(Thread, pk=pk, author=request.user)
    if request.method == "POST":
        thread.delete()
        messages.success(request, "Thread berhasil dihapus.")
        return redirect("community:index")
    return render(request, "community/delete.html", {"thread": thread})


@login_required
@require_POST
def like(request, pk):
    thread = get_object_or_404(Thread, pk=pk)
    action = request.POST.get("action")
    is_async = is_async_request(request)

    if is_async and action == "toggle":
        like_record, created = ThreadLike.objects.get_or_create(
            thread=thread,
            user=request.user,
        )
        if not created:
            like_record.delete()
    elif action == "unlike":
        ThreadLike.objects.filter(thread=thread, user=request.user).delete()
    elif action == "like":
        ThreadLike.objects.get_or_create(thread=thread, user=request.user)

    is_liked = ThreadLike.objects.filter(thread=thread, user=request.user).exists()
    like_count = ThreadLike.objects.filter(thread=thread).count()

    if is_htmx_request(request):
        thread.is_liked = is_liked
        thread.like_count = like_count
        return render(
            request,
            "community/like_control.html",
            {
                "thread": thread,
                "like_variant": request.POST.get("variant", "feed"),
            },
        )

    if is_async:
        return JsonResponse(
            {
                "is_liked": is_liked,
                "like_count": like_count,
            }
        )

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("community:detail", args=[pk])
    return redirect(next_url)
