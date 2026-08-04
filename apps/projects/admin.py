from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "stack", "default_model", "priority_weight", "updated_at")
    search_fields = ("name", "repo_url", "stack")
    list_filter = ("default_model",)
