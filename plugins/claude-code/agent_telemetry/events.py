"""Enrichment shared by all agent adapters.

Adapters normalize their native payloads into a common event shape; this module
wraps that with environment metadata and the raw payload for lossless capture.
"""

import datetime as _dt
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


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _host_metadata():
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    }
