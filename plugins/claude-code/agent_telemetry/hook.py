"""Entry point for the shared agent telemetry hook.

Usage: agent-telemetry-hook <agent>

Reads a single native hook payload as JSON on stdin, normalizes it via the
matching adapter, and appends an enriched JSONL event. The process always exits
0 and never writes to stdout so that a telemetry failure can never block or
alter an agent session.
"""

import json
import sys

from . import adapters, events, writer


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        _run(argv)
    except Exception:
        pass
    return 0


def _run(argv):
    agent = argv[0] if argv else None
    adapter = adapters.get_adapter(agent)
    if adapter is None:
        return
    payload = _read_payload()
    if payload is None:
        return
    event = events.build_event(agent, adapter.normalize(payload), payload)
    writer.append_event(event)


def _read_payload():
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparsed_stdin": raw}


if __name__ == "__main__":
    sys.exit(main())
