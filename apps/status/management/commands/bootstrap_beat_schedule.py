from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Garante o PeriodicTask de fallback do coletor de status (idempotente)."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=20,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="status.collect_all_status (fallback)",
            defaults={
                "task": "apps.status.tasks.collect_all_status",
                "interval": schedule,
                "enabled": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Beat schedule ok."))
