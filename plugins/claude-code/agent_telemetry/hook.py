"""Entry point for the shared telemetry hook.

Usage: agent-telemetry-hook <agent>

Reads one native hook payload as JSON on stdin and notes the session's
existence, nothing more. A hook collects no conversation: the payload is used
for its session id, working directory and record path, and is then discarded
rather than stored. The process always exits 0 and never writes to stdout, so a
telemetry failure can neither block nor alter an agent session.

One hook does more than that. A session that has been rated is written out
again at the events its adapter names -- the end of the session under Claude
Code, which is when it writes the cost, and the end of every turn under codex,
which accumulates usage as it goes.
"""

import json
import sys

from . import adapters, session


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
    session.observe(agent, adapter.normalize(payload))


def _read_payload():
    """The hook's own input, or None when there is nothing usable.

    Unparseable stdin is dropped rather than kept: it can hold anything at all,
    and with no event log there is nowhere it belongs.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    sys.exit(main())
