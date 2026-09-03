"""Append-only JSONL telemetry writer.

Each session appends to its own file, so sessions never interleave and a file is
only ever written by the one session that owns it. Every write is best-effort: a
telemetry failure must never interrupt an agent session, so all errors are
swallowed here rather than propagated to the caller.
"""

import json
import os

from . import paths


def append_event(event):
    """Append one event as a JSON line. Returns True on success, else False."""
    path = paths.log_path(event.get("session_id"))
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
