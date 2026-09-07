from django.contrib import admin

from .models import ChoreOccurrence, ChoreSchedule, FamilyMember


@admin.register(FamilyMember)
class FamilyMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(ChoreSchedule)
class ChoreScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "assignee",
        "recurrence",
        "next_due_at",
        "is_active",
    ]
    list_filter = ["recurrence", "is_active"]
    search_fields = ["title", "assignee__name"]


@admin.register(ChoreOccurrence)
class ChoreOccurrenceAdmin(admin.ModelAdmin):
    list_display = ["schedule", "assignee", "due_at", "completed"]
    list_filter = ["schedule__recurrence", "completed_at"]
    search_fields = ["schedule__title", "schedule__assignee__name"]

    @admin.display(description="ответственный")
    def assignee(self, occurrence):
        return occurrence.schedule.assignee

    @admin.display(boolean=True, description="выполнено")
    def completed(self, occurrence):
        return occurrence.is_completed
