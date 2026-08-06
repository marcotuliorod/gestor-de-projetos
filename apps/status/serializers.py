from rest_framework import serializers

from .models import StatusSnapshot


class StatusSnapshotSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = StatusSnapshot
        fields = [
            "id",
            "project",
            "project_name",
            "branch",
            "ahead",
            "behind",
            "open_prs",
            "ci_status",
            "last_commit",
            "changed_files",
            "checks",
            "coverage_pct",
            "state",
            "summary",
            "created_at",
        ]
