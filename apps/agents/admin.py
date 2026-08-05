from django.contrib import admin

from .models import TaskRun, TaskRunStep


class TaskRunStepInline(admin.TabularInline):
    model = TaskRunStep
    extra = 0
    readonly_fields = ("phase", "attempt", "status", "model_used", "started_at", "finished_at")
    can_delete = False


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = ("project", "state", "urgency", "model_used", "created_at")
    list_filter = ("state", "urgency")
    search_fields = ("project__name", "instruction")
    inlines = [TaskRunStepInline]


@admin.register(TaskRunStep)
class TaskRunStepAdmin(admin.ModelAdmin):
    list_display = ("task_run", "phase", "attempt", "status", "model_used", "created_at")
    list_filter = ("phase", "status")
