"""Append-only JSONL telemetry writer.

Every write is best-effort: a telemetry failure must never interrupt an agent
session, so all errors are swallowed here rather than propagated to the caller.
"""

import json
import os

LOG_PATH_ENV = "AGENT_TELEMETRY_LOG"
DEFAULT_LOG_NAME = "agent-telemetry.jsonl"


def log_path():
    return os.environ.get(LOG_PATH_ENV) or _default_log_path()


def _default_log_path():
    home = os.path.expanduser("~")
    # expanduser returns "~" unchanged when there is no home to resolve, which
    # would put the log in a literal "~" directory under the session cwd.
    return os.path.join(home, DEFAULT_LOG_NAME) if os.path.isabs(home) else None


def append_event(event):
    """Append one event as a JSON line. Returns True on success, else False."""
    path = log_path()
    if not path:
        return False
    try:
        return _write_line(path, event)
    except Exception:
        return False


def _write_line(path, event):
    line = json.dumps(event, ensure_ascii=False, default=str)
    _ensure_parent_dir(path)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return True


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
