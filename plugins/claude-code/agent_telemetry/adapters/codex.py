"""Codex adapter.

Codex hooks carry the same four lifecycle fields as Claude Code's -- session id,
working directory, event name, and a path to the session's own record -- so the
mapping below is nearly the same one. As with the other agents, nothing else is
taken from a payload: not the prompt, not `tool_input`, and not the payload.

Two things are different enough to be handled here. Codex records usage
continuously rather than only as a session ends, so a rated session is written
out at the end of every turn and not just at `SessionEnd`, whose budget is one
second by default and three at most. And `transcript_path` is documented as not
a stable interface -- the manual's own example names a rollout inside the
project -- so it is trusted only when it is really a file, and otherwise the
rollout is found by the session id its name ends with.

Reference for hook payloads: https://learn.chatgpt.com/docs/hooks
"""

import glob
import os

AGENT = "codex"

# Usage lands in the rollout as the session runs and there is no cost to wait
# for, so each turn's end is worth writing out; `SessionEnd` stays as the last
# word on a session that ends mid-turn.
FINALIZE_AT = ("turn_end", "session_end")

HOME_ENV = "CODEX_HOME"
DEFAULT_HOME = "~/.codex"

_EVENT_TYPES = {
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "Stop": "turn_end",
}


def user_instruction_dirs():
    """Where this agent loads the user's own instructions from: its own home."""
    return [home()]


def home():
    """`$CODEX_HOME`, or where codex keeps its home by default."""
    return os.environ.get(HOME_ENV) or os.path.expanduser(DEFAULT_HOME)


def normalize(payload):
    """The lifecycle fields, and where this agent says it keeps its own record."""
    return {
        "event_type": _EVENT_TYPES.get(payload.get("hook_event_name"), "other"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
    }


def locate_record(given, session_id):
    """The session's rollout, whether or not the payload named it correctly.

    `transcript_path` is explicitly not a stable interface, so it is used only
    when it names a file belonging to this session; failing that, codex's own
    layout is searched, every rollout being named for the session that wrote it.
    """
    if _belongs(given, session_id):
        return given
    return _rollout(session_id) or given


def _belongs(path, session_id):
    """True when `path` is a file this session's own id names.

    Existing is not enough. The example in codex's own hook documentation is
    `<project>/.codex/rollout.jsonl`, and a file sitting at a path like that
    would otherwise be read as this session's usage whatever session wrote it.
    """
    if not path or not session_id or not os.path.isfile(path):
        return False
    return os.path.basename(path).endswith(f"-{session_id}.jsonl")


def _rollout(session_id):
    """`sessions/<y>/<m>/<d>/rollout-<stamp>-<session_id>.jsonl`, newest first."""
    if not session_id:
        return None
    pattern = os.path.join(home(), "sessions", "**", f"rollout-*-{glob.escape(session_id)}.jsonl")
    found = sorted(glob.glob(pattern, recursive=True))
    return found[-1] if found else None
