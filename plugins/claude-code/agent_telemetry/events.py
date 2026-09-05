"""Enrichment shared by all agent adapters, and reading back what was written.

Adapters normalize their native payloads into a common event shape; this module
wraps that with environment metadata and the raw payload for lossless capture.
"""

import datetime as _dt
import json
import os
import socket
import uuid

from . import SCHEMA_VERSION


def build_event(agent, normalized, raw_payload):
    """Combine adapter output, environment metadata, and the raw payload."""
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "agent": agent,
        "host": _host_metadata(),
    }
    event.update(normalized)
    event["raw"] = raw_payload
    return event


def read_log(path):
    """Yield the events in one JSONL log, skipping any line that is not JSON.

    A log is appended to by a live session, so its last line can be half
    written; a reader that cannot tolerate that would fail at random.
    """
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            event = _parse(line)
            if event is not None:
                yield event


def _parse(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _host_metadata():
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    }
