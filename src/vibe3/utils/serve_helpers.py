"""Shared serve utilities for PID validation, tmux session management,
and job serialization.

Extracted from server/registry.py to break bidirectional coupling between
server (L2) and services (L3). Both layers can legally import from utils (L6).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.utils import OrchestraInstanceInfo

ORCHESTRA_TMUX_SESSION = "vibe3-orchestra-serve"


def validate_pid_file(pid_file: Path) -> tuple["OrchestraInstanceInfo | None", bool]:
    """Validate PID file and check if process is a running orchestra instance.

    Returns:
        tuple of (instance_info, is_running):
        - (None, False): No PID file or invalid format
        - (info, False): Valid PID file but process is dead/not orchestra
        - (info, True): Valid PID file and process is running orchestra
    """
    from vibe3.utils.orchestra_instance import read_instance_info, validate_instance

    info = read_instance_info(pid_file)
    if info is None:
        return None, False

    is_running = validate_instance(info)
    return info, is_running


def orchestra_tmux_session_exists() -> bool:
    """Return whether the orchestra tmux session currently exists."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", ORCHESTRA_TMUX_SESSION],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0


def extract_material_from_log(job: Any) -> str | None:
    """Extract governance material slug from log path filename.

    Log filename format: {material_slug}-{timestamp}-t{tick}.log
    Example: "roadmap-intake-20260628-010215-t5.log" -> "roadmap-intake"
    """
    log_path = getattr(job, "log_path", None)
    if not log_path:
        return None
    filename = Path(log_path).name
    # Match material slugs with hyphens: roadmap-intake, cron-supervisor, etc.
    match = re.fullmatch(
        r"([a-z]+(?:-[a-z]+)*)-\d{8}-\d{6}-t\d+\.log",
        filename,
    )
    if match:
        return match.group(1)
    return None


def job_to_dict(job: Any) -> dict[str, Any]:
    """Serialize an ActiveJob to a JSON-safe dictionary."""
    d = {
        "actor_id": job.actor_id,
        "job_type": job.job_type.value,
        "status": job.runtime_status or job.status.value,
        "issue_number": job.issue_number,
        "branch": job.branch,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "pid": job.pid,
        "log_path": job.log_path,
    }
    # For governance jobs, include material name for API consumers
    if job.job_type.value == "governance" and job.log_path:
        material = extract_material_from_log(job)
        if material:
            d["material"] = material
    return d
