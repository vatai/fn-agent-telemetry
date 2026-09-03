"""Filesystem layout for telemetry artifacts.

Everything lives under one telemetry directory so the event log and the
transcript snapshots stay together:

    <AGENT_TELEMETRY_DIR>/agent-telemetry.jsonl
    <AGENT_TELEMETRY_DIR>/transcripts/<session_id>.jsonl

`AGENT_TELEMETRY_LOG` and `AGENT_TELEMETRY_TRANSCRIPT_DIR` override either
artifact individually. Both derive from the telemetry directory rather than from
each other, so overriding one leaves the other where it was.
"""

import os

TELEMETRY_DIR_ENV = "AGENT_TELEMETRY_DIR"
LOG_PATH_ENV = "AGENT_TELEMETRY_LOG"
TRANSCRIPT_DIR_ENV = "AGENT_TELEMETRY_TRANSCRIPT_DIR"

DEFAULT_DIR_NAME = "agent-telemetry"
LOG_NAME = "agent-telemetry.jsonl"
TRANSCRIPT_DIR_NAME = "transcripts"


def telemetry_dir():
    return os.environ.get(TELEMETRY_DIR_ENV) or _default_telemetry_dir()


def _default_telemetry_dir():
    home = os.path.expanduser("~")
    # expanduser returns "~" unchanged when there is no home to resolve, which
    # would put telemetry in a literal "~" directory under the session cwd.
    return os.path.join(home, DEFAULT_DIR_NAME) if os.path.isabs(home) else None


def log_path():
    return os.environ.get(LOG_PATH_ENV) or _under_telemetry_dir(LOG_NAME)


def transcript_dir():
    return os.environ.get(TRANSCRIPT_DIR_ENV) or _under_telemetry_dir(TRANSCRIPT_DIR_NAME)


def _under_telemetry_dir(name):
    directory = telemetry_dir()
    return os.path.join(directory, name) if directory else None
