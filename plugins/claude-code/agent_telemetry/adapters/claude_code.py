"""Claude Code adapter.

Maps native Claude Code hook payloads (delivered on stdin, one per hook event)
into the shared telemetry taxonomy while retaining every native field via the
raw payload captured upstream. Reference for payload fields:
https://docs.claude.com/en/docs/claude-code/hooks
"""

AGENT = "claude-code"

# The transcript is finished as the session ends -- the cost lands in its last
# line -- so a rated session is worth packing a second time once it is over.
REPACK_AT_SESSION_END = True

_EVENT_TYPES = {
    "SessionStart": "session_start",
    "SessionEnd": "session_end",
    "UserPromptSubmit": "user_prompt",
    "PreToolUse": "tool_pre",
    "PostToolUse": "tool_post",
    "Stop": "turn_end",
    "SubagentStop": "subagent_end",
    "Notification": "notification",
    "PreCompact": "compact",
}


def normalize(payload):
    """Return the shared event fields for one Claude Code hook payload."""
    native_event = payload.get("hook_event_name", "")
    normalized = {
        "event_type": _EVENT_TYPES.get(native_event, "unknown"),
        "native_event": native_event,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
        "transcript_path": payload.get("transcript_path"),
    }
    normalized.update(_event_details(native_event, payload))
    return normalized


def _event_details(native_event, payload):
    extractor = _DETAIL_EXTRACTORS.get(native_event)
    return extractor(payload) if extractor else {}


def _prompt_details(payload):
    return {"prompt": payload.get("prompt")}


def _pre_tool_details(payload):
    return {
        "tool_name": payload.get("tool_name"),
        "tool_input": payload.get("tool_input"),
    }


def _post_tool_details(payload):
    return {
        "tool_name": payload.get("tool_name"),
        "tool_input": payload.get("tool_input"),
        "tool_response": payload.get("tool_response"),
    }


def _session_start_details(payload):
    return {"source": payload.get("source")}


def _session_end_details(payload):
    return {"reason": payload.get("reason")}


def _notification_details(payload):
    return {"message": payload.get("message")}


def _compact_details(payload):
    return {
        "trigger": payload.get("trigger"),
        "custom_instructions": payload.get("custom_instructions"),
    }


_DETAIL_EXTRACTORS = {
    "UserPromptSubmit": _prompt_details,
    "PreToolUse": _pre_tool_details,
    "PostToolUse": _post_tool_details,
    "SessionStart": _session_start_details,
    "SessionEnd": _session_end_details,
    "Notification": _notification_details,
    "PreCompact": _compact_details,
}
