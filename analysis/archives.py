"""Read collected telemetry archives back into one row per session.

The archive is the interface: a zip holding `events.jsonl` and, usually,
`transcript.jsonl`. Nothing here imports the plugins' `agent_telemetry`
package, and nothing parses the archive filename -- `agent` and `session_id`
are on every event, so the same reader works whatever an archive is called.

What a row costs to build is decided by where each number lives. Counts of
prompts, turns and tool calls come from the events; tokens and cost reach no
hook payload and come from the transcript, whose shape is the agent's own. Two
of those shapes need care:

Claude Code writes one transcript line per content block and replicates the
whole `message.usage` onto each, so a message that thought before answering
appears twice with identical counts. Summing per line double-counts exactly the
messages that did the most work; the rows below sum one usage per `message.id`.

Cost is reported by neither agent the same way. opencode carries `cost` on every
assistant message, so a session total is a sum -- and a genuine `0` from a free
model is not missing data. Claude Code reports it only in a `cost-state` record,
which a short session may never contain, so its cost is `None` rather than `0`
when no such record was archived.

A stored `scale` is the authority for reading its own `value`. Archives predate
changes to the feedback vocabulary, so an old row is read with the scale it was
written against, and flagged when that scale is missing keys the current one has.
`fom` is free text and its `value` is in whatever unit that session used, so the
two do not compare across sessions; `satisfaction` is the field that does, being
the same 1-5 normalisation of whatever figure was measured. Rows written before
it was asked for carry `None`.

One asymmetry is not corrected here, only named: `/fn-eval` packs the archive in
the middle of the turn it runs in. opencode repacks at the end of every turn and
so captures that turn; Claude Code does not, so its archives are short the
rating turn's `turn_end`, its assistant messages and the seconds it took. Turn
counts, and anything per turn, are not comparable between the two agents.
"""

import collections
import datetime as _dt
import json
import os
import zipfile

TELEMETRY_DIR_ENV = "AGENT_TELEMETRY_DIR"
DEFAULT_DIR_NAME = "agent-telemetry"
EVENTS_MEMBER = "events.jsonl"
TRANSCRIPT_MEMBER = "transcript.jsonl"

TOKEN_FIELDS = ("input", "output", "reasoning", "cache_read", "cache_write")
# `reasoning` is the thinking part of `output`, not a sixth kind of token, so a
# total that added it in would count it twice.
BILLED_FIELDS = ("input", "output", "cache_read", "cache_write")
FEEDBACK_FIELDS = (
    "subject", "fom", "value", "unit", "better", "scale",
    "satisfaction", "comment", "legacy_scale",
)


def sessions(directory=None):
    """One row per archive in `directory`, oldest session first."""
    rows = [read_archive(path) for path in archive_paths(directory)]
    return sorted(rows, key=lambda row: row["started"] or "")


def telemetry_dir():
    return os.environ.get(TELEMETRY_DIR_ENV) or os.path.join(
        os.path.expanduser("~"), DEFAULT_DIR_NAME
    )


def archive_paths(directory=None):
    directory = directory or telemetry_dir()
    if not os.path.isdir(directory):
        return []
    names = sorted(name for name in os.listdir(directory) if name.endswith(".zip"))
    return [os.path.join(directory, name) for name in names]


def read_archive(path):
    """Flatten one archive into a row of session, activity, usage and rating."""
    with zipfile.ZipFile(path) as archive:
        events = _read_member(archive, EVENTS_MEMBER)
        transcript = _read_member(archive, TRANSCRIPT_MEMBER)
    row = {"archive": os.path.basename(path)}
    row.update(_session(events))
    row.update(_activity(events))
    row.update(_usage(row["agent"], transcript))
    row.update(_feedback(events))
    return row


def _read_member(archive, name):
    """Parse one JSONL member, skipping any line that is not JSON."""
    if name not in archive.namelist():
        return []
    lines = archive.read(name).decode("utf-8", "replace").splitlines()
    return [record for record in map(_parse, lines) if record is not None]


def _parse(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def _session(events):
    first, last = (events[0], events[-1]) if events else ({}, {})
    host = first.get("host") or {}
    return {
        "agent": first.get("agent"),
        "session_id": first.get("session_id"),
        "user": host.get("user"),
        "hostname": host.get("hostname"),
        "cwd": first.get("cwd"),
        "started": first.get("timestamp"),
        "ended": last.get("timestamp"),
        "duration_s": _elapsed(first.get("timestamp"), last.get("timestamp")),
        "events": len(events),
    }


def _elapsed(start, end):
    start, end = _time(start), _time(end)
    return round((end - start).total_seconds(), 1) if start and end else None


def _time(timestamp):
    try:
        return _dt.datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None


def _activity(events):
    counts = collections.Counter(event.get("event_type") for event in events)
    return {
        "prompts": counts["user_prompt"],
        "turns": counts["turn_end"],
        "tools": counts["tool_post"],
        "tools_unfinished": counts["tool_pre"] - counts["tool_post"] - _packing_call(events),
        "permission_asks": counts["permission_ask"],
        "notifications": counts["notification"],
        "compacts": counts["compact"],
        "subagents": counts["subagent_end"],
        "top_tools": _top_tools(events),
    }


def _packing_call(events):
    """1 when the archive was packed inside the `/fn-eval` tool call's own window.

    The rating is written from a tool call whose `tool_post` is recorded only
    once that call returns -- after the zip has been closed. An agent that
    repacks at the end of the turn picks the line up; one that packs and stops
    never can, so without this every archive of its would report a phantom
    unfinished call, and a real denied one would be invisible among them.
    """
    calls = [event for event in events if event.get("event_type") in ("tool_pre", "tool_post")]
    rated = any(event.get("event_type") == "feedback" for event in events)
    return 1 if rated and calls and calls[-1].get("event_type") == "tool_pre" else 0


def _top_tools(events, limit=3):
    names = (event.get("tool_name") for event in events if event.get("event_type") == "tool_post")
    counts = collections.Counter(name for name in names if name)
    return ", ".join(f"{name}x{count}" for name, count in counts.most_common(limit))


def _usage(agent, transcript):
    readers = {"claude-code": _claude_usage, "opencode": _opencode_usage}
    reader = readers.get(agent)
    return reader(transcript) if reader and transcript else _no_usage()


def _no_usage():
    return _totals([], None, [])


def _claude_usage(transcript):
    """Sum one usage per `message.id`; a line per content block repeats it."""
    by_message, models = {}, []
    for record in transcript:
        if record.get("type") != "assistant":
            continue
        message = record.get("message") or {}
        models.append(message.get("model"))
        by_message.setdefault(message.get("id"), _claude_tokens(message.get("usage") or {}))
    return _totals(by_message.values(), _claude_cost(transcript), models)


def _claude_tokens(usage):
    return {
        "input": usage.get("input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
        "reasoning": (usage.get("output_tokens_details") or {}).get("thinking_tokens") or 0,
        "cache_read": usage.get("cache_read_input_tokens") or 0,
        "cache_write": usage.get("cache_creation_input_tokens") or 0,
    }


def _claude_cost(transcript):
    """`cost-state` is written at checkpoints, so take the largest, not the last."""
    costs = [
        record.get("totalCostUSD")
        for record in transcript
        if record.get("type") == "cost-state" and record.get("totalCostUSD") is not None
    ]
    return max(costs) if costs else None


def _opencode_usage(transcript):
    messages = [record.get("info") or {} for record in transcript]
    replies = [info for info in messages if info.get("role") == "assistant"]
    cost = sum(info.get("cost") or 0 for info in replies) if replies else None
    tokens = (_opencode_tokens(info.get("tokens") or {}) for info in replies)
    return _totals(tokens, cost, [_opencode_model(info) for info in replies])


def _opencode_model(info):
    """Provider and model together: the same model id can come from either."""
    return "/".join(part for part in (info.get("providerID"), info.get("modelID")) if part)


def _opencode_tokens(tokens):
    cache = tokens.get("cache") or {}
    return {
        "input": tokens.get("input") or 0,
        "output": tokens.get("output") or 0,
        "reasoning": tokens.get("reasoning") or 0,
        "cache_read": cache.get("read") or 0,
        "cache_write": cache.get("write") or 0,
    }


def _totals(per_message, cost, models):
    totals = {field: 0 for field in TOKEN_FIELDS}
    for tokens in per_message:
        for field in TOKEN_FIELDS:
            totals[field] += tokens[field]
    totals["total"] = sum(totals[field] for field in BILLED_FIELDS)
    totals["cost_usd"] = cost
    totals["models"] = ", ".join(dict.fromkeys(name for name in models if name))
    return totals


def _feedback(events):
    """The session's rating, read through the scale it was written against."""
    rated = [event for event in events if event.get("event_type") == "feedback"]
    if not rated:
        return dict.fromkeys(FEEDBACK_FIELDS)
    answer = rated[-1]
    scale = answer.get("scale") or {}
    fields = {
        name: answer.get(name)
        for name in ("subject", "fom", "value", "satisfaction", "comment")
    }
    return fields | {
        "unit": scale.get("unit"),
        "better": scale.get("better"),
        "scale": describe_scale(scale),
        # Ratings collected before measured figures existed carry a 1-5 scale
        # whatever the figure, so their value cannot be read as a measurement.
        "legacy_scale": "unit" not in scale,
    }


def describe_scale(scale):
    """A free-form figure has no direction to report, so that clause is dropped."""
    if not scale:
        return None
    bound = f"{scale['min']}-{scale['max']}" if scale.get("max") else f"{scale.get('min')}+"
    unit = f" {scale['unit']}" if scale.get("unit") else ""
    better = f", {scale['better']} is better" if scale.get("better") else ""
    return f"{bound}{unit}{better}"
