from django.contrib import admin

from .models import StatusSnapshot


@admin.register(StatusSnapshot)
class StatusSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "state", "branch", "open_prs", "created_at")
    list_filter = ("state",)
    search_fields = ("project__name", "branch")
    date_hierarchy = "created_at"
