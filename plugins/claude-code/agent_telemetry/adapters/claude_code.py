"""Claude Code adapter.

Maps native Claude Code hook payloads onto the handful of lifecycle facts this
package acts on. Nothing else is taken from a payload: no prompt, no tool input
or response, and not the payload itself -- `Stop` alone carries the assistant's
entire reply in `last_assistant_message`, so keeping payloads wholesale is how
conversation gets collected by accident.

Reference for payload fields: https://docs.claude.com/en/docs/claude-code/hooks
"""

import os

AGENT = "claude-code"

# The cost lands in the record only as the session ends, so a rated session is
# worth one more pass once it is over -- and only then, the record holding
# nothing new until it is.
FINALIZE_AT = ("session_end",)

_EVENT_TYPES = {
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "Stop": "turn_end",
}


def user_instruction_dirs():
    """Where this agent loads the user's own instructions from."""
    return [os.path.join(os.path.expanduser("~"), ".claude")]


def normalize(payload):
    """The lifecycle fields, and where this agent keeps its own session record."""
    return {
        "event_type": _EVENT_TYPES.get(payload.get("hook_event_name"), "other"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
    }
