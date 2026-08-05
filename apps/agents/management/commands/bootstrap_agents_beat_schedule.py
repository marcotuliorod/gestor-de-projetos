from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Garante o PeriodicTask da fila noturna de agentes (idempotente)."

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="2",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="agents.dispatch_nightly_queue",
            defaults={
                "task": "apps.agents.tasks.dispatch_nightly_queue",
                "crontab": schedule,
                "enabled": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Beat schedule da fila noturna ok."))
