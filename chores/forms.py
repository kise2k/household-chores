from django import forms
from django.utils import timezone

from .models import ChoreSchedule, FamilyMember


class FamilyMemberForm(forms.ModelForm):
    class Meta:
        model = FamilyMember
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "placeholder": "Например, Саша",
                }
            ),
        }

    def clean_name(self):
        return self.cleaned_data["name"].strip()


class ChoreScheduleForm(forms.ModelForm):
    next_due_at = forms.DateTimeField(
        label="Первый срок выполнения",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
        help_text=(
            "Для еженедельного дела день недели определяется по этой дате."
        ),
    )

    class Meta:
        model = ChoreSchedule
        fields = ["title", "assignee", "next_due_at", "recurrence"]
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "Например, вынести мусор"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].empty_label = "Выберите участника"

    def clean_title(self):
        return self.cleaned_data["title"].strip()

    def clean_next_due_at(self):
        due_at = self.cleaned_data["next_due_at"]
        if due_at <= timezone.now():
            raise forms.ValidationError("Укажите дату и время в будущем.")
        return due_at
