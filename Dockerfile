FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps kept minimal; psycopg[binary] ships its own libpq.
# git is required by apps.agents.workspace (worktree/mirror management).
# bubblewrap+socat are required for the Agent SDK's sandbox={"enabled": True}
# (apps.agents.agent_client) to actually isolate Bash commands — without
# them the SDK silently runs unsandboxed (confirmed by testing: an agent
# could `cat` any file on the container's filesystem, e.g. `.env`).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git bubblewrap socat \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Claude Agent SDK's --dangerously-skip-permissions (permission_mode=
# "bypassPermissions", used headlessly by apps.agents.agent_client) refuses
# to run as root/sudo. Also just generally good practice for a container.
# /data/repos is pre-created+chowned here so the named volume mounted there
# inherits this ownership on first use.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data/repos \
    && chown -R appuser:appuser /app /data/repos
USER appuser

EXPOSE 8000

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
