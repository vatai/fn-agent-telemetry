"""opencode adapter.

Maps the payloads assembled by `plugins/opencode/plugin/agent-telemetry.js` onto
the same lifecycle facts. As with Claude Code, nothing else is taken -- not the
prompt, not tool arguments or results, not the payload.

opencode keeps its messages in a database rather than a file, so there is no
record path to report: its plugin reads usage back over the SDK and hands it to
`agent_telemetry.messages` directly.

Reference for hook and event shapes: https://opencode.ai/docs/plugins/
"""

AGENT = "opencode"

# `session.deleted` is a session the user threw away, not one that finished, and
# the plugin has already refreshed usage at the end of every turn.
FINALIZE_AT_SESSION_END = False

_EVENT_TYPES = {
    "session.created": "session_start",
    "session.deleted": "session_end",
    "session.idle": "turn_end",
}


def normalize(payload):
    return {
        "event_type": _EVENT_TYPES.get(payload.get("hook"), "other"),
        "session_id": payload.get("sessionID"),
        "cwd": payload.get("directory"),
        "transcript_path": None,
    }
