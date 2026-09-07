"""Usage for an agent that keeps no session record on disk.

Usage: agent_telemetry.messages --session <session_id>

Claude Code writes a record of its own and names it in every hook payload.
opencode keeps its messages in a database instead, so its plugin reads them back
over the SDK at the end of each turn and hands them here as one JSON array on
stdin. Only the token counts and cost are taken from them; the messages
themselves are never written anywhere.

A turn also ends after the one `/fn-eval` runs in, and the document written
halfway through that turn is short its usage. So a session already carrying a
rating is written out again here. Rating is still what produces output; this
only keeps it from going stale.

Driven by a plugin rather than a person: always exits 0 and writes nothing to
stdout, so a telemetry failure cannot disturb a session.
"""

import argparse
import json
import sys

from . import document, session, usage
from .adapters import opencode


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        _run(argv)
    except Exception:
        pass
    return 0


def _run(argv):
    session_id = _parse_args(argv).session
    doc = document.load(session_id)
    if doc is None:
        return
    rows, cost = usage.from_opencode_messages(json.loads(sys.stdin.read()))
    doc["usage"] = rows
    doc["cost_usd"] = cost
    document.save(session_id, doc)
    if document.rated(doc):
        session.finalize(session_id, opencode.AGENT)


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-telemetry-messages")
    parser.add_argument("--session", required=True, help="session the messages belong to")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
