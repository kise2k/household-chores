from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


not_blank = RegexValidator(
    regex=r".*\S.*",
    message="Это поле не может состоять только из пробелов.",
)


class FamilyMember(models.Model):
    name = models.CharField(
        "имя",
        max_length=100,
        unique=True,
        validators=[not_blank],
    )
    created_at = models.DateTimeField("добавлен", auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "участник семьи"
        verbose_name_plural = "участники семьи"

    def __str__(self):
        return self.name


class ChoreSchedule(models.Model):
    class Recurrence(models.TextChoices):
        ONE_TIME = "one-time", "Без повтора"
        DAILY = "daily", "Ежедневно"
        WEEKLY = "weekly", "Еженедельно"

    title = models.CharField(
        "название",
        max_length=200,
        validators=[not_blank],
    )
    assignee = models.ForeignKey(
        FamilyMember,
        verbose_name="ответственный",
        on_delete=models.PROTECT,
        related_name="chore_schedules",
    )
    recurrence = models.CharField(
        "повторение",
        max_length=10,
        choices=Recurrence.choices,
        default=Recurrence.ONE_TIME,
    )
    next_due_at = models.DateTimeField("ближайший срок")
    is_active = models.BooleanField("активно", default=True)
    created_at = models.DateTimeField("создано", auto_now_add=True)

    class Meta:
        ordering = ["next_due_at", "title"]
        verbose_name = "расписание дела"
        verbose_name_plural = "расписания дел"

    def __str__(self):
        return f"{self.title} — {self.assignee}"


class ChoreOccurrence(models.Model):
    schedule = models.ForeignKey(
        ChoreSchedule,
        verbose_name="расписание",
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    due_at = models.DateTimeField("срок выполнения")
    completed_at = models.DateTimeField(
        "выполнено",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField("создано", auto_now_add=True)

    class Meta:
        ordering = ["due_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "due_at"],
                name="unique_chore_occurrence_due_at",
            ),
        ]
        verbose_name = "экземпляр дела"
        verbose_name_plural = "экземпляры дел"

    @property
    def is_completed(self):
        return self.completed_at is not None

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_at < timezone.now()

    def __str__(self):
        return f"{self.schedule.title} — {self.due_at:%d.%m.%Y %H:%M}"
