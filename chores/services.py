from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ChoreOccurrence, ChoreSchedule


RECURRENCE_INTERVALS = {
    ChoreSchedule.Recurrence.DAILY: timedelta(days=1),
    ChoreSchedule.Recurrence.WEEKLY: timedelta(weeks=1),
}


def generate_due_occurrences(through=None):
    """Create every due recurring occurrence up to ``through``.

    Existing occurrences are preserved and skipped, so the function is safe to
    run repeatedly. Each schedule is advanced to its first future deadline.
    """

    through = through or timezone.now()
    created_count = 0

    with transaction.atomic():
        schedules = (
            ChoreSchedule.objects.select_for_update()
            .filter(
                is_active=True,
                recurrence__in=RECURRENCE_INTERVALS,
                next_due_at__lte=through,
            )
            .order_by("pk")
        )

        for schedule in schedules:
            interval = RECURRENCE_INTERVALS[schedule.recurrence]
            due_at = schedule.next_due_at

            while due_at <= through:
                _, created = ChoreOccurrence.objects.get_or_create(
                    schedule=schedule,
                    due_at=due_at,
                )
                created_count += int(created)
                due_at += interval

            schedule.next_due_at = due_at
            schedule.save(update_fields=["next_due_at"])

    return created_count
