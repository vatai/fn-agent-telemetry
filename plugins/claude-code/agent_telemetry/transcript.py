"""The conversation record of an agent that keeps no transcript file.

Usage: agent_telemetry.transcript --session <session_id>

Claude Code writes a transcript of its own and names it in every hook payload.
opencode keeps its messages in a database instead, so its plugin reads them back
over the SDK at the end of each turn and hands them here as one JSON array on
stdin. They are written to the path the opencode adapter already reports as
`transcript_path`, one message per line, so the archived member means the same
thing whichever agent produced it.

A turn also ends after the one `/fn-eval` runs in, and that turn is missing from
the archive packed halfway through it. So a session that already carries a
rating is repacked here. Rating is still what creates an archive; this only
keeps an archive from going stale.

Like the hooks, this is driven by a plugin rather than by a person: it always
exits 0 and writes nothing to stdout, so a telemetry failure cannot disturb a
session.
"""

import argparse
import json
import os
import sys
import tempfile

from . import feedback, paths, snapshot


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        _run(argv)
    except Exception:
        pass
    return 0


def _run(argv):
    session_id = _parse_args(argv).session
    path = paths.transcript_path(session_id)
    if not path:
        return
    _write(path, _lines(json.loads(sys.stdin.read())))
    if feedback.rated(session_id):
        snapshot.snapshot(session_id, path)


def _lines(messages):
    return "".join(json.dumps(m, ensure_ascii=False, default=str) + "\n" for m in messages)


def _write(path, text):
    """Stage and rename, so a half-written dump never replaces a whole one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as staging:
            staging.write(text)
        os.replace(staged, path)
    except Exception:
        _remove(staged)
        raise


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-telemetry-transcript")
    parser.add_argument("--session", required=True, help="session the messages belong to")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
