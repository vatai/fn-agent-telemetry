"""Filesystem layout for telemetry artifacts.

One archive per session is the output, holding both of that session's files:

    <AGENT_TELEMETRY_DIR>/<date>-<time>-<session_id>.zip
        events.jsonl        one JSON object per hook event
        transcript.jsonl    copy of the session's own conversation record

The archive is named for when the session started, not for when it was packed,
so a directory listing sorts chronologically and repacking a session replaces
its archive instead of adding another.

Hook events arrive one process at a time and a zip cannot be appended to, so the
event log accumulates in a working file under `.pending/` and is folded into the
archive at every snapshot. An agent that keeps no transcript file of its own
dumps one next to that log, which is why the two are told apart by name here.

`AGENT_TELEMETRY_DIR` is the only knob; everything else is derived from it.
"""

import datetime as _dt
import os
import re

TELEMETRY_DIR_ENV = "AGENT_TELEMETRY_DIR"

DEFAULT_DIR_NAME = "agent-telemetry"
PENDING_DIR_NAME = ".pending"
LOG_SUFFIX = ".jsonl"
TRANSCRIPT_SUFFIX = ".transcript.jsonl"
ARCHIVE_SUFFIX = ".zip"
ARCHIVE_STAMP_FORMAT = "%Y%m%d-%H%M%S"
EVENTS_MEMBER = "events.jsonl"
TRANSCRIPT_MEMBER = "transcript.jsonl"
UNKNOWN_SESSION = "unknown-session"

_UNSAFE_IN_NAME = re.compile(r"[^A-Za-z0-9._-]")


def telemetry_dir():
    return os.environ.get(TELEMETRY_DIR_ENV) or _default_telemetry_dir()


def _default_telemetry_dir():
    home = os.path.expanduser("~")
    # expanduser returns "~" unchanged when there is no home to resolve, which
    # would put telemetry in a literal "~" directory under the session cwd.
    return os.path.join(home, DEFAULT_DIR_NAME) if os.path.isabs(home) else None


def pending_dir():
    directory = telemetry_dir()
    return os.path.join(directory, PENDING_DIR_NAME) if directory else None


def log_path(session_id):
    """Working event log for a session, folded into the archive at each snapshot."""
    return _pending_path(session_id, LOG_SUFFIX)


def transcript_path(session_id):
    """Where an agent that keeps no transcript file of its own dumps one.

    Claude Code names its transcript in every hook payload and never needs this;
    opencode keeps its messages in a database, so its plugin dumps them here at
    the end of each turn and its adapter reports this path in place of a native
    one.
    """
    return _pending_path(session_id, TRANSCRIPT_SUFFIX)


def is_log(name):
    """Event logs and dumped transcripts share `.jsonl` and share a directory."""
    return name.endswith(LOG_SUFFIX) and not name.endswith(TRANSCRIPT_SUFFIX)


def archive_path(session_id, started_at=None):
    """`<date>-<time>-<session_id>.zip`, stamped with when the session started."""
    directory = telemetry_dir()
    if not directory:
        return None
    name = _stamp(started_at) + "-" + _session_name(session_id) + ARCHIVE_SUFFIX
    return os.path.join(directory, name)


def _pending_path(session_id, suffix):
    directory = pending_dir()
    return os.path.join(directory, _session_name(session_id) + suffix) if directory else None


def _stamp(started_at):
    return (started_at or _dt.datetime.now()).strftime(ARCHIVE_STAMP_FORMAT)


def _session_name(session_id):
    """Reduce a session id to a bare filename; ids come from the agent, not us."""
    name = _UNSAFE_IN_NAME.sub("_", session_id or "").strip(".")
    return name or UNKNOWN_SESSION
