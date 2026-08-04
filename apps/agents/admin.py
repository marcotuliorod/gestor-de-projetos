from django.contrib import admin

from .models import TaskRun


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = ("project", "state", "urgency", "model_used", "created_at")
    list_filter = ("state", "urgency")
    search_fields = ("project__name", "instruction")
