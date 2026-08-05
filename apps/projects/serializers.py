from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "repo_url",
            "repo_owner",
            "repo_name",
            "stack",
            "build_command",
            "test_command",
            "lint_command",
            "default_model",
            "priority_weight",
            "agent_permissions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "repo_owner", "repo_name", "created_at", "updated_at"]
