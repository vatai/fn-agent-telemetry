"""The example inputs the plugins are run against.

Hand-built and small enough to read, because each record here stands for a rule
in `dev-notes.md` rather than for a real session:

- a message written as two content-block records, whose usage must be summed
  once (`msg_1`), against two that are one record each;
- two `cost-state` records with the larger written first, so taking the last
  would report the wrong cost;
- a `tool_use` id that appears twice, which must count as one call;
- a `Skill` call, the one call whose input is read, for `uses` on a skill;
- a `skill_listing` that a later one adds a name to, which must fold;
- codex's cumulative `token_count` snapshots, including the repeat an aborted
  turn writes, which must add no row;
- codex tool calls in both of its shapes, one of them repeated;
- codex's `world_state` listing, whose entries name a file on disk.

`SENTINEL` marks every field that carries conversation: a prompt, an assistant
reply, a tool's input, a tool's result. It is in the inputs so that
`test_no_conversation.py` can require it to be absent from everything written.

A hook payload here carries every conversation-bearing field any of its agent's
events carries, rather than only the ones that event really has. The payloads
are the union deliberately: what matters is that none of it is stored.
"""

SENTINEL = "CONVERSATION-b4d1f7"

SESSION_ID = "610153d8-b1f9-48dc-b2e6-43b8febca643"
OTHER_SESSION_ID = "0f0e0d0c-0b0a-4090-8070-605040302010"

SKILL_TEXT = "---\nname: fn-eval\n---\n\nRate the session.\n"


def codex_rollout_name(session_id=SESSION_ID):
    """A rollout's name. Every one is named for the session that wrote it, which
    is how the adapter finds one when the payload's path cannot be trusted."""
    return f"rollout-2026-09-09T10-00-00-{session_id}.jsonl"


# --- hook payloads ----------------------------------------------------------


def claude_payload(event, cwd, record_path, session_id=SESSION_ID):
    """A Claude Code hook payload. Four fields are used; the rest are dropped."""
    return {
        "hook_event_name": event,
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": record_path,
    } | _conversation_fields()


def codex_payload(event, cwd, record_path, session_id=SESSION_ID):
    """A codex hook payload: the same four lifecycle fields, same treatment."""
    return {
        "hook_event_name": event,
        "session_id": session_id,
        "cwd": cwd,
        "transcript_path": record_path,
    } | _conversation_fields()


def opencode_payload(hook, cwd, session_id=SESSION_ID):
    """What the opencode plugin pipes: its event name, and the event's properties."""
    return {
        "hook": hook,
        "directory": cwd,
        "sessionID": session_id,
        "info": {"title": SENTINEL},
    }


def _conversation_fields():
    """Everything a payload carries that must reach no file."""
    return {
        "prompt": SENTINEL,
        "last_assistant_message": SENTINEL,
        "tool_name": "Bash",
        "tool_input": {"command": SENTINEL},
        "tool_response": {"stdout": SENTINEL},
    }


# --- Claude Code's own record -----------------------------------------------

MSG_1_USAGE = {
    "input_tokens": 2,
    "output_tokens": 452,
    "output_tokens_details": {"thinking_tokens": 276},
    "cache_read_input_tokens": 129339,
    "cache_creation_input_tokens": 974,
}
MSG_2_USAGE = {"input_tokens": 4, "output_tokens": 60, "cache_read_input_tokens": 130313}
MSG_3_USAGE = {"input_tokens": 1, "output_tokens": 18, "cache_read_input_tokens": 130373}

MODEL = "claude-opus-5"

# The rows the record below must produce: one per `message.id`, in the order the
# messages were written, and never one per content-block record.
CLAUDE_USAGE = [
    {
        "message_id": "msg_1",
        "model": MODEL,
        "input": 2,
        "output": 452,
        "reasoning": 276,
        "cache_read": 129339,
        "cache_write": 974,
    },
    {
        "message_id": "msg_2",
        "model": MODEL,
        "input": 4,
        "output": 60,
        "reasoning": 0,
        "cache_read": 130313,
        "cache_write": 0,
    },
    {
        "message_id": "msg_3",
        "model": MODEL,
        "input": 1,
        "output": 18,
        "reasoning": 0,
        "cache_read": 130373,
        "cache_write": 0,
    },
]

CLAUDE_COST = 4.13

# Two calls of `Bash` -- the repeated id counting once -- and two of `Skill`.
CLAUDE_TOOLS = [{"name": "Bash", "calls": 2}, {"name": "Skill", "calls": 2}]

# The skill the record invokes without it appearing in any listing.
UNLISTED_SKILL = "unlisted-skill"


def claude_record():
    """Claude Code's transcript, as far as the three collectors are concerned."""
    return [
        {"type": "user", "message": {"role": "user", "content": SENTINEL}},
        _listing(["code-review"], "- code-review: Review the current diff for bugs"),
        # One message, two records, the whole message's usage repeated on each.
        _assistant("msg_1", MSG_1_USAGE, [_text(SENTINEL)]),
        _assistant("msg_1", MSG_1_USAGE, [_tool_use("call_1", "Bash", {"command": SENTINEL})]),
        # A record that repeats a call already counted, which must not inflate it.
        _assistant("msg_2", MSG_2_USAGE, [_tool_use("call_1", "Bash", {"command": SENTINEL})]),
        _assistant("msg_2", MSG_2_USAGE, [_tool_use("call_2", "Bash", {"command": SENTINEL})]),
        # A plugin arrived mid-session, so a second listing adds to the first.
        _listing(["code-review", "fn-eval"], "- fn-eval: Rate this session"),
        # Two `Skill` calls: one for a listed skill, and one for a skill no
        # listing mentions, which is kept as used rather than dropped.
        _assistant(
            "msg_3",
            MSG_3_USAGE,
            [
                _tool_use("call_3", "Skill", {"skill": "code-review"}),
                _tool_use("call_4", "Skill", {"skill": UNLISTED_SKILL}),
            ],
        ),
        # The larger cost first: a session resumed after one was written writes
        # another, so the largest is the session's cost and the last is not.
        {"type": "cost-state", "totalCostUSD": CLAUDE_COST},
        {"type": "cost-state", "totalCostUSD": 1.02},
    ]


def _assistant(message_id, usage, content):
    message = {"id": message_id, "model": MODEL, "usage": usage, "content": content}
    return {"type": "assistant", "message": message}


def _text(body):
    return {"type": "text", "text": body}


def _tool_use(call_id, name, arguments):
    return {"type": "tool_use", "id": call_id, "name": name, "input": arguments}


def _listing(names, content):
    listing = {"type": "skill_listing", "names": names, "content": content}
    return {"type": "user", "attachment": listing}


# --- codex's own rollout ----------------------------------------------------

CODEX_MODEL = "gpt-5-codex"

# Codex reports the session's counts so far on every snapshot, so a row is what
# they grew by, a repeated snapshot is no row, and `input` has both cached kinds
# taken out of it. No `message_id`: codex attributes usage to a request.
CODEX_USAGE = [
    {
        "message_id": None,
        "model": CODEX_MODEL,
        "input": 200,
        "output": 50,
        "reasoning": 20,
        "cache_read": 800,
        "cache_write": 0,
    },
    {
        "message_id": None,
        "model": CODEX_MODEL,
        "input": 400,
        "output": 40,
        "reasoning": 10,
        "cache_read": 1100,
        "cache_write": 0,
    },
]

CODEX_TOOLS = [{"name": "apply_patch", "calls": 1}, {"name": "shell", "calls": 1}]


def codex_record(skills_root):
    """A codex rollout. `skills_root` is where its listing says its skills live."""
    return [
        {"type": "turn_context", "payload": {"model": CODEX_MODEL}},
        _codex_state(skills_root),
        _codex_call("function_call", "shell", "call_a", SENTINEL),
        # The same call again: counted once per `call_id`, over both shapes.
        _codex_call("function_call", "shell", "call_a", SENTINEL),
        _codex_call("custom_tool_call", "apply_patch", "call_b", SENTINEL),
        {"type": "response_item", "payload": {"type": "message", "content": [_text(SENTINEL)]}},
        _codex_snapshot(input_tokens=1000, cached=800, output=50, reasoning=20),
        # An aborted turn re-reports the previous snapshot: nothing grew, no row.
        _codex_snapshot(input_tokens=1000, cached=800, output=50, reasoning=20),
        _codex_snapshot(input_tokens=2500, cached=1900, output=90, reasoning=30),
    ]


def codex_decoy_record():
    """A rollout belonging to another session, at the path codex's docs show.

    Its counts are nothing like this session's, so reading it instead would be
    obvious in the result rather than plausible.
    """
    return [
        {"type": "turn_context", "payload": {"model": "someone-elses-model"}},
        _codex_snapshot(input_tokens=999999, cached=0, output=999, reasoning=99),
    ]


def _codex_call(kind, name, call_id, command):
    """A codex tool call. Its `arguments` are what it ran, so they are not read."""
    payload = {"type": kind, "name": name, "call_id": call_id, "arguments": command}
    return {"type": "response_item", "payload": payload}


def _codex_snapshot(input_tokens, cached, output, reasoning):
    """`token_count`, carrying the whole session's usage so far."""
    counts = {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "reasoning_output_tokens": reasoning,
    }
    usage = {"type": "token_count", "info": {"total_token_usage": counts}}
    return {"type": "event_msg", "payload": usage}


def _codex_state(skills_root):
    """The `host_skills` body codex shows the model, naming files through roots."""
    body = "\n".join(
        (
            "Available skills:",
            f"- `r0` = `{skills_root}`",
            "- fn-eval: Rate this session (file: r0/fn-eval/SKILL.md)",
            "- unpacked: A skill with no file of its own",
        )
    )
    state = {"host_skills": {"body": body}}
    return {"type": "world_state", "payload": {"state": state}}


# --- what the opencode SDK returns ------------------------------------------

OPENCODE_MODEL = "anthropic/claude-opus-5"

OPENCODE_USAGE = [
    {
        "message_id": "msg_o1",
        "model": OPENCODE_MODEL,
        "input": 12,
        "output": 340,
        "reasoning": 25,
        "cache_read": 900,
        "cache_write": 7,
    }
]

OPENCODE_COST = 0.021

OPENCODE_TOOLS = [{"name": "bash", "calls": 1}, {"name": "read", "calls": 1}]


def opencode_messages():
    """The messages the plugin reads back over the SDK and hands to Python."""
    return [
        {"info": {"role": "user", "id": "msg_o0"}, "parts": [_text(SENTINEL)]},
        {
            "info": {
                "role": "assistant",
                "id": "msg_o1",
                "providerID": "anthropic",
                "modelID": "claude-opus-5",
                "cost": OPENCODE_COST,
                "tokens": {
                    "input": 12,
                    "output": 340,
                    "reasoning": 25,
                    "cache": {"read": 900, "write": 7},
                },
            },
            "parts": [
                _text(SENTINEL),
                _opencode_tool("bash", "part_a"),
                # The same part twice, as a rewritten message repeats it.
                _opencode_tool("bash", "part_a"),
                _opencode_tool("read", "part_b"),
            ],
        },
    ]


def _opencode_tool(tool, call_id):
    state = {"input": {"command": SENTINEL}, "output": SENTINEL}
    return {"type": "tool", "tool": tool, "callID": call_id, "state": state}
