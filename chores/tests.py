from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ChoreScheduleForm, FamilyMemberForm
from .models import ChoreOccurrence, ChoreSchedule, FamilyMember
from .services import generate_due_occurrences


class FamilyMemberTests(TestCase):
    def test_member_can_be_added_from_shared_page(self):
        response = self.client.post(
            reverse("chores:member_list"),
            {"name": "  Саша  "},
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assertTrue(FamilyMember.objects.filter(name="Саша").exists())

        response = self.client.get(reverse("chores:member_list"))
        self.assertContains(response, "Саша")

    def test_whitespace_only_name_is_rejected(self):
        form = FamilyMemberForm({"name": "   "})

        self.assertFalse(form.is_valid())
        self.assertFalse(FamilyMember.objects.exists())

    def test_unassigned_member_can_be_deleted(self):
        member = FamilyMember.objects.create(name="Маша")

        response = self.client.post(
            reverse("chores:member_delete", args=[member.pk])
        )

        self.assertRedirects(response, reverse("chores:member_list"))
        self.assertFalse(FamilyMember.objects.filter(pk=member.pk).exists())

    def test_member_with_a_chore_cannot_be_deleted(self):
        member = FamilyMember.objects.create(name="Маша")
        ChoreSchedule.objects.create(
            title="Полить цветы",
            assignee=member,
            next_due_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.post(
            reverse("chores:member_delete", args=[member.pk]),
            follow=True,
        )

        self.assertContains(response, "Нельзя удалить участника")
        self.assertTrue(FamilyMember.objects.filter(pk=member.pk).exists())


class ChoreViewTests(TestCase):
    def setUp(self):
        self.member = FamilyMember.objects.create(name="Саша")
        self.future_due = timezone.localtime(
            timezone.now() + timedelta(days=1)
        ).replace(second=0, microsecond=0)

    def create_occurrence(self, title, due_at, completed_at=None):
        schedule = ChoreSchedule.objects.create(
            title=title,
            assignee=self.member,
            next_due_at=due_at,
        )
        return ChoreOccurrence.objects.create(
            schedule=schedule,
            due_at=due_at,
            completed_at=completed_at,
        )

    def test_creating_chore_creates_schedule_and_first_occurrence(self):
        response = self.client.post(
            reverse("chores:chore_create"),
            {
                "title": "  Вынести мусор  ",
                "assignee": self.member.pk,
                "next_due_at": self.future_due.strftime("%Y-%m-%dT%H:%M"),
                "recurrence": ChoreSchedule.Recurrence.DAILY,
            },
        )

        self.assertRedirects(response, reverse("chores:chore_list"))
        schedule = ChoreSchedule.objects.get()
        occurrence = ChoreOccurrence.objects.get()
        self.assertEqual(schedule.title, "Вынести мусор")
        self.assertEqual(schedule.assignee, self.member)
        self.assertEqual(schedule.recurrence, ChoreSchedule.Recurrence.DAILY)
        self.assertEqual(occurrence.due_at, schedule.next_due_at)

    def test_chore_form_rejects_blank_title_and_past_deadline(self):
        past_due = timezone.localtime(
            timezone.now() - timedelta(hours=1)
        ).replace(second=0, microsecond=0)
        form = ChoreScheduleForm(
            {
                "title": "   ",
                "assignee": self.member.pk,
                "next_due_at": past_due.strftime("%Y-%m-%dT%H:%M"),
                "recurrence": ChoreSchedule.Recurrence.ONE_TIME,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertIn("next_due_at", form.errors)

    def test_overdue_state_depends_on_deadline_and_completion(self):
        overdue = self.create_occurrence(
            "Помыть посуду",
            timezone.now() - timedelta(hours=1),
        )
        completed = self.create_occurrence(
            "Убрать стол",
            timezone.now() - timedelta(hours=2),
            completed_at=timezone.now(),
        )

        self.assertTrue(overdue.is_overdue)
        self.assertFalse(overdue.is_completed)
        self.assertFalse(completed.is_overdue)
        self.assertTrue(completed.is_completed)

    def test_chore_can_be_marked_completed(self):
        occurrence = self.create_occurrence(
            "Вынести мусор",
            self.future_due,
        )

        response = self.client.post(
            reverse("chores:chore_complete", args=[occurrence.pk])
        )

        self.assertRedirects(response, reverse("chores:chore_list"))
        occurrence.refresh_from_db()
        self.assertIsNotNone(occurrence.completed_at)

    def test_list_can_be_filtered_by_status_and_assignee(self):
        other_member = FamilyMember.objects.create(name="Маша")
        overdue = self.create_occurrence(
            "Просроченное дело",
            timezone.now() - timedelta(hours=1),
        )
        other_schedule = ChoreSchedule.objects.create(
            title="Чужое просроченное дело",
            assignee=other_member,
            next_due_at=timezone.now() - timedelta(hours=2),
        )
        ChoreOccurrence.objects.create(
            schedule=other_schedule,
            due_at=other_schedule.next_due_at,
        )
        self.create_occurrence("Будущее дело", self.future_due)

        response = self.client.get(
            reverse("chores:chore_list"),
            {"status": "overdue", "assignee": self.member.pk},
        )

        self.assertContains(response, overdue.schedule.title)
        self.assertNotContains(response, "Чужое просроченное дело")
        self.assertNotContains(response, "Будущее дело")


class RecurrenceTests(TestCase):
    def setUp(self):
        self.member = FamilyMember.objects.create(name="Саша")
        self.through = timezone.now().replace(microsecond=0)

    def make_schedule(self, recurrence, first_due_at):
        schedule = ChoreSchedule.objects.create(
            title="Регулярное дело",
            assignee=self.member,
            recurrence=recurrence,
            next_due_at=first_due_at,
        )
        first_occurrence = ChoreOccurrence.objects.create(
            schedule=schedule,
            due_at=first_due_at,
        )
        return schedule, first_occurrence

    def test_daily_occurrences_are_generated_and_previous_stays_open(self):
        first_due = self.through - timedelta(days=2)
        schedule, first_occurrence = self.make_schedule(
            ChoreSchedule.Recurrence.DAILY,
            first_due,
        )

        created_count = generate_due_occurrences(through=self.through)

        schedule.refresh_from_db()
        first_occurrence.refresh_from_db()
        self.assertEqual(created_count, 2)
        self.assertEqual(schedule.occurrences.count(), 3)
        self.assertIsNone(first_occurrence.completed_at)
        self.assertEqual(
            schedule.next_due_at,
            self.through + timedelta(days=1),
        )

    def test_weekly_occurrences_are_generated(self):
        first_due = self.through - timedelta(weeks=2)
        schedule, _ = self.make_schedule(
            ChoreSchedule.Recurrence.WEEKLY,
            first_due,
        )

        created_count = generate_due_occurrences(through=self.through)

        schedule.refresh_from_db()
        self.assertEqual(created_count, 2)
        self.assertEqual(schedule.occurrences.count(), 3)
        self.assertEqual(
            schedule.next_due_at,
            self.through + timedelta(weeks=1),
        )

    def test_repeated_generation_does_not_create_duplicates(self):
        schedule, _ = self.make_schedule(
            ChoreSchedule.Recurrence.DAILY,
            self.through - timedelta(days=1),
        )

        generate_due_occurrences(through=self.through)
        second_created_count = generate_due_occurrences(through=self.through)

        self.assertEqual(second_created_count, 0)
        self.assertEqual(schedule.occurrences.count(), 2)

    def test_inactive_and_one_time_schedules_are_ignored(self):
        inactive, _ = self.make_schedule(
            ChoreSchedule.Recurrence.DAILY,
            self.through - timedelta(days=1),
        )
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        one_time, _ = self.make_schedule(
            ChoreSchedule.Recurrence.ONE_TIME,
            self.through - timedelta(days=1),
        )

        created_count = generate_due_occurrences(through=self.through)

        self.assertEqual(created_count, 0)
        self.assertEqual(inactive.occurrences.count(), 1)
        self.assertEqual(one_time.occurrences.count(), 1)

    def test_management_command_runs_generator(self):
        schedule, _ = self.make_schedule(
            ChoreSchedule.Recurrence.DAILY,
            self.through - timedelta(days=1),
        )
        output = StringIO()

        call_command(
            "generate_chore_occurrences",
            through=self.through.isoformat(),
            stdout=output,
        )

        self.assertEqual(schedule.occurrences.count(), 2)
        self.assertIn("Создано экземпляров дел: 1", output.getvalue())

    def test_management_command_rejects_invalid_datetime(self):
        with self.assertRaises(CommandError):
            call_command(
                "generate_chore_occurrences",
                through="not-a-date",
            )
