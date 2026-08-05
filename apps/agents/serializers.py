from rest_framework import serializers

from .models import TaskRun, TaskRunStep


class TaskRunStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskRunStep
        fields = ["id", "phase", "attempt", "status", "model_used", "detail", "started_at", "finished_at"]


class TaskRunSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    steps = TaskRunStepSerializer(many=True, read_only=True)

    class Meta:
        model = TaskRun
        fields = [
            "id",
            "project",
            "project_name",
            "instruction",
            "urgency",
            "state",
            "model_used",
            "summary",
            "pr_url",
            "branch_name",
            "created_at",
            "updated_at",
            "steps",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "state",
            "model_used",
            "summary",
            "pr_url",
            "branch_name",
            "created_at",
            "updated_at",
            "steps",
        ]
