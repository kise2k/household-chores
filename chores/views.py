from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ChoreScheduleForm, FamilyMemberForm
from .models import ChoreOccurrence, FamilyMember


CHORE_STATUSES = {"all", "upcoming", "overdue", "completed"}


def chore_list(request):
    status = request.GET.get("status", "all")
    if status not in CHORE_STATUSES:
        status = "all"

    occurrences = ChoreOccurrence.objects.select_related(
        "schedule",
        "schedule__assignee",
    )
    members = FamilyMember.objects.all()
    selected_assignee = None
    assignee_id = request.GET.get("assignee")

    if assignee_id:
        selected_assignee = FamilyMember.objects.filter(pk=assignee_id).first()
        if selected_assignee:
            occurrences = occurrences.filter(
                schedule__assignee=selected_assignee
            )

    now = timezone.now()
    summary = {
        "all": occurrences.count(),
        "upcoming": occurrences.filter(
            completed_at__isnull=True,
            due_at__gte=now,
        ).count(),
        "overdue": occurrences.filter(
            completed_at__isnull=True,
            due_at__lt=now,
        ).count(),
        "completed": occurrences.filter(
            completed_at__isnull=False
        ).count(),
    }

    if status == "upcoming":
        occurrences = occurrences.filter(
            completed_at__isnull=True,
            due_at__gte=now,
        )
    elif status == "overdue":
        occurrences = occurrences.filter(
            completed_at__isnull=True,
            due_at__lt=now,
        )
    elif status == "completed":
        occurrences = occurrences.filter(completed_at__isnull=False)

    return render(
        request,
        "chores/chore_list.html",
        {
            "occurrences": occurrences,
            "members": members,
            "selected_assignee": selected_assignee,
            "selected_status": status,
            "summary": summary,
        },
    )


@require_http_methods(["GET", "POST"])
def member_list(request):
    form = FamilyMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        member = form.save()
        messages.success(request, f"Участник «{member.name}» добавлен.")
        return redirect("chores:member_list")

    members = FamilyMember.objects.annotate(
        schedule_count=Count("chore_schedules")
    )
    return render(
        request,
        "chores/member_list.html",
        {"form": form, "members": members},
    )


@require_POST
def member_delete(request, pk):
    member = get_object_or_404(FamilyMember, pk=pk)
    try:
        member.delete()
    except ProtectedError:
        messages.error(
            request,
            "Нельзя удалить участника, пока ему назначены дела.",
        )
    else:
        messages.success(request, f"Участник «{member.name}» удалён.")
    return redirect("chores:member_list")


@require_http_methods(["GET", "POST"])
def chore_create(request):
    form = ChoreScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            schedule = form.save()
            ChoreOccurrence.objects.create(
                schedule=schedule,
                due_at=schedule.next_due_at,
            )
        messages.success(request, f"Дело «{schedule.title}» создано.")
        return redirect("chores:chore_list")

    return render(request, "chores/chore_form.html", {"form": form})


@require_POST
def chore_complete(request, pk):
    occurrence = get_object_or_404(ChoreOccurrence, pk=pk)
    if occurrence.completed_at is None:
        occurrence.completed_at = timezone.now()
        occurrence.save(update_fields=["completed_at"])
        messages.success(
            request,
            f"Дело «{occurrence.schedule.title}» отмечено выполненным.",
        )

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(reverse("chores:chore_list"))
