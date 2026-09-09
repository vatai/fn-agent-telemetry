"""Which tools a session ran, and how many times each.

Names and counts, and nothing else. A tool's input and its result are never
stored -- with one exception, stated here because it is the only one: a `Skill`
call's input is read for the name of the skill it invoked, so a session can say
which skills it actually *used* and not merely which were available. That name
is counted and the input discarded, the same way the record is read for usage
and never kept. A `SlashCommand` call carries the typed command line in its
input, which is conversation, so no input but a `Skill`'s is looked at.

Claude Code writes a tool call as a `tool_use` block on an assistant record,
opencode as a `tool` part on a message, and codex as a `function_call` or
`custom_tool_call` item in its rollout. All repeat: Claude Code rewrites a
message as it grows, the way it does for usage, so a block is counted once per
block id, a part once per `callID`, and a codex item once per `call_id`.

Only Claude Code names the skill a call invoked, so only it reports skill uses:
codex has no `Skill` tool to read, and a codex call's own field would be the
shell command it ran.

A subagent's tools are not counted. They are written to a record of its own,
which nothing here opens.
"""

import collections

from . import jsonl

SKILL_TOOL = "Skill"

# The two shapes a codex rollout writes a tool call in: a function tool, and a
# freeform one such as `exec` or `apply_patch`.
CODEX_CALL_TYPES = ("function_call", "custom_tool_call")


def from_claude_record(path):
    """`([{name, calls}], {skill: calls})` -- tools run, and skills invoked."""
    calls, skills = collections.Counter(), collections.Counter()
    for block in _tool_use_blocks(path):
        calls[block.get("name")] += 1
        skill = _invoked_skill(block)
        if skill:
            skills[skill] += 1
    return _rows(calls), dict(skills)


def from_codex_record(path):
    """`([{name, calls}], None)` for codex's own rollout: no skill uses to report.

    Two fields are read off a call, its name and its id, and nothing else: a
    codex call carries what it ran in `input` or `arguments` -- the shell
    command, the patch -- which is exactly what is never collected.
    """
    calls, seen = collections.Counter(), set()
    for record in jsonl.records(path):
        if record.get("type") != "response_item":
            continue
        item = record.get("payload") or {}
        if item.get("type") not in CODEX_CALL_TYPES:
            continue
        if _unseen(seen, item.get("call_id")):
            calls[item.get("name")] += 1
    return _rows(calls), None


def from_opencode_messages(messages):
    """`[{name, calls}]` for the messages opencode's SDK returned."""
    calls = collections.Counter()
    for part in _tool_parts(messages):
        calls[part.get("tool")] += 1
    return _rows(calls)


def _tool_use_blocks(path):
    seen = set()
    for record in jsonl.records(path):
        if record.get("type") != "assistant":
            continue
        for block in (record.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                if _unseen(seen, block.get("id")):
                    yield block


def _tool_parts(messages):
    seen = set()
    for message in messages or []:
        for part in (message or {}).get("parts") or []:
            if isinstance(part, dict) and part.get("type") == "tool":
                if _unseen(seen, part.get("callID")):
                    yield part


def _unseen(seen, identity):
    """True the first time an identified call is offered. An unidentified one always counts."""
    if identity is None:
        return True
    if identity in seen:
        return False
    seen.add(identity)
    return True


def _invoked_skill(block):
    if block.get("name") != SKILL_TOOL:
        return None
    arguments = block.get("input")
    name = arguments.get("skill") if isinstance(arguments, dict) else None
    return name.strip() if isinstance(name, str) and name.strip() else None


def _rows(calls):
    """Most-called first, so a row reads as what the session mostly did."""
    counted = [(name, count) for name, count in calls.items() if name]
    counted.sort(key=lambda pair: (-pair[1], pair[0]))
    return [{"name": name, "calls": count} for name, count in counted]
