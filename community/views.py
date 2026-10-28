from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import ReplyForm, ThreadForm
from .models import Thread

def threads_for(user):
    return Thread.objects.select_related("author").annotate(
        like_count=Count("liked_by", distinct=True),
        reply_count=Count("replies", distinct=True),
        is_liked=Exists(Thread.liked_by.through.objects.filter(thread_id=OuterRef("pk"), user_id=user.pk)),
    ).order_by("-created_at", "pk")


@login_required
def index(request):
    category = request.GET.get("category", "")
    threads = threads_for(request.user)
    if category in Thread.Category.values:
        threads = threads.filter(category=category)
    else:
        category = ""
    return render(request, "community/index.html", {
        "page_obj": Paginator(threads, 8).get_page(request.GET.get("page")),
        "category": category,
        "thread_total": Thread.objects.count(),
        "member_total": Thread.objects.values("author").distinct().count(),
        "achievement_total": Thread.objects.filter(category="achievement").count(),
    })


@login_required
def detail(request, pk):
    thread = get_object_or_404(threads_for(request.user), pk=pk)
    form = ReplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reply = form.save(commit=False)
        reply.author, reply.thread = request.user, thread
        reply.save()
        messages.success(request, "Balasanmu sudah ikut menumbuhkan obrolan. Terima kasih!")
        return redirect("community:detail", pk=pk)
    return render(request, "community/detail.html", {"thread": thread, "form": form,
        "replies": thread.replies.select_related("author").order_by("created_at", "pk")})


@login_required
def thread_form(request, pk=None):
    thread = get_object_or_404(Thread, pk=pk, author=request.user, achievement_event_id__isnull=True) if pk else None
    form = ThreadForm(request.POST or None, instance=thread)
    if request.method == "POST" and form.is_valid():
        thread = form.save(commit=False)
        thread.author = request.user
        thread.save()
        messages.success(request, "Cerita berhasil disimpan. Satu cerita, banyak inspirasi!")
        return redirect("community:detail", pk=thread.pk)
    return render(request, "community/form.html", {"form": form, "thread": thread})

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
    # Explicit desired state makes retried requests idempotent.
    if request.POST.get("action") == "unlike":
        thread.liked_by.remove(request.user)
    elif request.POST.get("action") == "like":
        thread.liked_by.add(request.user)
    return redirect("community:detail", pk=pk)
