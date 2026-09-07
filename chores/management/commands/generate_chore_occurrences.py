from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from chores.services import generate_due_occurrences


class Command(BaseCommand):
    help = "Создаёт наступившие экземпляры повторяющихся домашних дел."

    def add_arguments(self, parser):
        parser.add_argument(
            "--through",
            help=(
                "Создать дела до указанного момента в формате ISO 8601. "
                "По умолчанию используется текущее время."
            ),
        )

    def handle(self, *args, **options):
        through = timezone.now()
        if options["through"]:
            through = parse_datetime(options["through"])
            if through is None:
                raise CommandError(
                    "Не удалось распознать --through. Используйте ISO 8601."
                )
            if timezone.is_naive(through):
                through = timezone.make_aware(
                    through,
                    timezone.get_current_timezone(),
                )

        created_count = generate_due_occurrences(through=through)
        self.stdout.write(
            self.style.SUCCESS(
                f"Создано экземпляров дел: {created_count}."
            )
        )
