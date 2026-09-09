"""opencode adapter.

Maps the payloads assembled by `plugins/opencode/plugin/agent-telemetry.js` onto
the same lifecycle facts. As with Claude Code, nothing else is taken -- not the
prompt, not tool arguments or results, not the payload.

opencode keeps its messages in a database rather than a file, so there is no
record path to report: its plugin reads usage back over the SDK and hands it to
`agent_telemetry.messages` directly.

Reference for hook and event shapes: https://opencode.ai/docs/plugins/
"""

import os

AGENT = "opencode"

# Nothing here: `session.deleted` is a session the user threw away rather than
# one that finished, and the plugin has already refreshed usage and written a
# rated session out at the end of every turn.
FINALIZE_AT = ()

_EVENT_TYPES = {
    "session.created": "session_start",
    "session.deleted": "session_end",
    "session.idle": "turn_end",
}


def user_instruction_dirs():
    """Where this agent loads the user's own instructions from.

    Two directories, not one: opencode reads `AGENTS.md` from its own global
    config directory -- `$XDG_CONFIG_HOME` or `~/.config`, then the app name --
    *and* `~/.claude/CLAUDE.md`, unless `disableClaudeCodePrompt` turns the
    latter off. Both are collected, since a session ran under both.
    """
    config = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return [os.path.join(config, "opencode"), os.path.join(os.path.expanduser("~"), ".claude")]


def normalize(payload):
    return {
        "event_type": _EVENT_TYPES.get(payload.get("hook"), "other"),
        "session_id": payload.get("sessionID"),
        "cwd": payload.get("directory"),
        "transcript_path": None,
    }
