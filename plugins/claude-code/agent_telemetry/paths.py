"""Filesystem layout for telemetry artifacts.

Everything lives under one telemetry directory, keyed by session so that no two
sessions ever share a file:

    <AGENT_TELEMETRY_DIR>/events/<session_id>.jsonl
    <AGENT_TELEMETRY_DIR>/transcripts/<session_id>.jsonl

`AGENT_TELEMETRY_DIR` is the only knob; everything else is derived from it.
"""

import os
import re

TELEMETRY_DIR_ENV = "AGENT_TELEMETRY_DIR"

DEFAULT_DIR_NAME = "agent-telemetry"
EVENTS_DIR_NAME = "events"
TRANSCRIPTS_DIR_NAME = "transcripts"
UNKNOWN_SESSION = "unknown-session"

_UNSAFE_IN_NAME = re.compile(r"[^A-Za-z0-9._-]")


def telemetry_dir():
    return os.environ.get(TELEMETRY_DIR_ENV) or _default_telemetry_dir()


def _default_telemetry_dir():
    home = os.path.expanduser("~")
    # expanduser returns "~" unchanged when there is no home to resolve, which
    # would put telemetry in a literal "~" directory under the session cwd.
    return os.path.join(home, DEFAULT_DIR_NAME) if os.path.isabs(home) else None


def events_dir():
    return _under_telemetry_dir(EVENTS_DIR_NAME)


def transcripts_dir():
    return _under_telemetry_dir(TRANSCRIPTS_DIR_NAME)


def log_path(session_id):
    return _session_file(events_dir(), session_id)


def transcript_path(session_id):
    return _session_file(transcripts_dir(), session_id)


def _under_telemetry_dir(name):
    directory = telemetry_dir()
    return os.path.join(directory, name) if directory else None


def _session_file(directory, session_id):
    return os.path.join(directory, _session_name(session_id) + ".jsonl") if directory else None


def _session_name(session_id):
    """Reduce a session id to a bare filename; ids come from the agent, not us."""
    name = _UNSAFE_IN_NAME.sub("_", session_id or "").strip(".")
    return name or UNKNOWN_SESSION
