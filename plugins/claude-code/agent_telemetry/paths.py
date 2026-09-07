"""Filesystem layout for telemetry output.

One JSON document per rated session is the whole output:

    <AGENT_TELEMETRY_DIR>/<date>-<time>-<session_id>.json

named for when the session started, so a listing sorts chronologically and
re-rating a session overwrites its own document instead of adding another. The
document is assembled over the life of a session -- context at the start, usage
and cost at the end, the rating in between -- so a partial one accumulates at
`.pending/<session_id>.json` in the same shape until the session is rated.

`AGENT_TELEMETRY_DIR` is the only knob; everything else is derived from it.
"""

import datetime as _dt
import os
import re

TELEMETRY_DIR_ENV = "AGENT_TELEMETRY_DIR"

DEFAULT_DIR_NAME = "agent-telemetry"
PENDING_DIR_NAME = ".pending"
DOCUMENT_SUFFIX = ".json"
STAMP_FORMAT = "%Y%m%d-%H%M%S"
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


def pending_path(session_id):
    """The document being assembled for a session that is not yet rated."""
    directory = pending_dir()
    if not directory:
        return None
    return os.path.join(directory, _session_name(session_id) + DOCUMENT_SUFFIX)


def output_path(session_id, started_at=None):
    """`<date>-<time>-<session_id>.json`, stamped with when the session started."""
    directory = telemetry_dir()
    if not directory:
        return None
    name = _stamp(started_at) + "-" + _session_name(session_id) + DOCUMENT_SUFFIX
    return os.path.join(directory, name)


def is_pending_document(name):
    return name.endswith(DOCUMENT_SUFFIX)


def _stamp(started_at):
    return (started_at or _dt.datetime.now()).strftime(STAMP_FORMAT)


def _session_name(session_id):
    """Reduce a session id to a bare filename; ids come from the agent, not us."""
    name = _UNSAFE_IN_NAME.sub("_", session_id or "").strip(".")
    return name or UNKNOWN_SESSION
