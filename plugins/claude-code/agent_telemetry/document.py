"""The session document: read it, change it, write it whole.

One JSON object per session holds everything collected. It is built up as the
session runs and rewritten whole at each change -- there is no append-only log
here, because nothing is collected per event.

Every write is staged and renamed into place, so an interrupted write can never
replace a good document with half of one. Like everything else in this package,
a failure is swallowed: telemetry must not interrupt a session.
"""

import datetime as _dt
import json
import os
import tempfile

from . import SCHEMA_VERSION, paths


def blank(session_id, agent):
    """A document with the session block filled in and nothing collected yet."""
    return {
        "schema_version": SCHEMA_VERSION,
        "session": {
            "session_id": session_id,
            "agent": agent,
            "cwd": None,
            "started": None,
            "ended": None,
            "host": _host(),
        },
        "skills": [],
        "tools": [],
        "usage": [],
        "cost_usd": None,
        "context": [],
        "feedback": None,
    }


def load(session_id):
    """The pending document for a session, or None if there is not one."""
    path = paths.pending_path(session_id)
    if not path or not os.path.isfile(path):
        return None
    return read(path)


def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        return document if isinstance(document, dict) else None
    except (OSError, ValueError):
        return None


def save(session_id, document):
    """Write the pending document. Returns True on success."""
    path = paths.pending_path(session_id)
    if not path:
        return False
    try:
        write(path, document)
        return True
    except Exception:
        return False


def write(path, document):
    """Stage beside the destination, then rename, so a reader sees one or the other."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as staging:
            json.dump(document, staging, ensure_ascii=False, indent=1, default=str)
            staging.write("\n")
        os.replace(staged, path)
    except Exception:
        _remove(staged)
        raise


def rated(document):
    return bool((document or {}).get("feedback"))


def touch(document, cwd=None, started=False, ended=False):
    """Record when the session was seen, and where it is running."""
    session = document.setdefault("session", {})
    now = now_iso()
    if cwd and not session.get("cwd"):
        session["cwd"] = cwd
    if started or not session.get("started"):
        session["started"] = session.get("started") or now
    if ended or not session.get("ended"):
        session["ended"] = now
    if ended:
        session["ended"] = now
    return document


def started_at(document):
    """When the session started, in local time, for naming its output file."""
    stamp = ((document or {}).get("session") or {}).get("started")
    try:
        return _dt.datetime.fromisoformat(stamp).astimezone()
    except (TypeError, ValueError):
        return None


def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _host():
    import socket

    return {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    }


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
