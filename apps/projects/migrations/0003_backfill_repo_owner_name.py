from django.db import migrations

from apps.projects.github_utils import parse_github_repo_url


def backfill(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    for project in Project.objects.exclude(repo_url=""):
        parsed = parse_github_repo_url(project.repo_url)
        if parsed:
            project.repo_owner, project.repo_name = parsed
            project.save(update_fields=["repo_owner", "repo_name"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0002_project_repo_name_project_repo_owner"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
