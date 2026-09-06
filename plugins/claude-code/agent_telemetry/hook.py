"""Entry point for the shared agent telemetry hook.

Usage: agent-telemetry-hook <agent>

Reads a single native hook payload as JSON on stdin, normalizes it via the
matching adapter, and appends an enriched JSONL event. The process always exits
0 and never writes to stdout so that a telemetry failure can never block or
alter an agent session.

One hook does more than write its event: a session that ends after being rated
is repacked, since the agent finishes writing the transcript -- cost included --
only once the session is over.
"""

import json
import sys

from . import adapters, events, feedback, snapshot, writer


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
    _repack_ended_session(event)


def _repack_ended_session(event):
    """Refresh a rated session's archive once the session is over.

    Claude Code writes its `cost-state` record only as a session ends, so the
    archive `/fn-eval` packed mid-session can never hold the session's cost.
    Rating is still what creates an archive; this only keeps one from going
    stale, the same way the opencode plugin's end-of-turn dump does.
    """
    session_id = event.get("session_id")
    if event.get("event_type") != "session_end" or not session_id:
        return
    if feedback.rated(session_id):
        snapshot.snapshot(session_id, event.get("transcript_path"))


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
