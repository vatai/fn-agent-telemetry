"""opencode adapter.

Maps opencode plugin-hook and bus-event payloads into the shared telemetry
taxonomy. The payloads are assembled by the JS plugin under `plugins/opencode`,
which names each one in `hook` and supplies the working directory, since no
opencode payload carries one of its own.

opencode keeps its messages in a database rather than a transcript file, so
`transcript_path` names the copy its plugin dumps at the end of every turn --
see `agent_telemetry.transcript`.

Permission prompts have no Claude Code counterpart and are recorded anyway: how
often a session had to stop and ask is a signal nothing else carries. Claude
Code's `subagent_end` has no counterpart here.
Reference for hook and event shapes: https://opencode.ai/docs/plugins/
"""

from .. import paths

AGENT = "opencode"

# `session_end` here is `session.deleted`, a session the user threw away, not one
# that finished; the plugin has already repacked at the end of every turn.
REPACK_AT_SESSION_END = False

_EVENT_TYPES = {
    "session.created": "session_start",
    "session.deleted": "session_end",
    "session.idle": "turn_end",
    "session.compacted": "compact",
    "session.error": "notification",
    "chat.message": "user_prompt",
    "tool.execute.before": "tool_pre",
    "tool.execute.after": "tool_post",
    "permission.ask": "permission_ask",
}


def normalize(payload):
    """Return the shared event fields for one opencode hook payload."""
    native_event = payload.get("hook", "")
    session_id = payload.get("sessionID")
    normalized = {
        "event_type": _EVENT_TYPES.get(native_event, "unknown"),
        "native_event": native_event,
        "session_id": session_id,
        "cwd": payload.get("directory"),
        "transcript_path": paths.transcript_path(session_id),
    }
    normalized.update(_event_details(native_event, payload))
    return normalized


def _event_details(native_event, payload):
    extractor = _DETAIL_EXTRACTORS.get(native_event)
    return extractor(payload) if extractor else {}


def _prompt_details(payload):
    return {"prompt": _prompt_text(payload.get("parts"))}


def _prompt_text(parts):
    """A user message is a list of parts; only the text ones are the prompt."""
    texts = [part.get("text") for part in parts or [] if part.get("type") == "text"]
    return "\n".join(text for text in texts if text) or None


def _pre_tool_details(payload):
    return {
        "tool_name": payload.get("tool"),
        "tool_input": payload.get("args"),
    }


def _post_tool_details(payload):
    return {
        "tool_name": payload.get("tool"),
        "tool_input": payload.get("args"),
        "tool_response": payload.get("result"),
    }


def _error_details(payload):
    error = payload.get("error") or {}
    return {"message": error.get("name") or error.get("message")}


def _permission_details(payload):
    permission = payload.get("permission") or {}
    return {
        "tool_name": permission.get("type"),
        "message": permission.get("title"),
        "status": payload.get("status"),
    }


_DETAIL_EXTRACTORS = {
    "chat.message": _prompt_details,
    "tool.execute.before": _pre_tool_details,
    "tool.execute.after": _post_tool_details,
    "session.error": _error_details,
    "permission.ask": _permission_details,
}
