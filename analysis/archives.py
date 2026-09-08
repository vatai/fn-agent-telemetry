"""Read collected telemetry back into one row per session.

Two formats sit side by side, and which one a file is decides how it is read.
A `.json` document is the current form: skills, per-message usage, cost, the
`AGENTS.md`/`CLAUDE.md` in effect, which tools ran and how often, and the
rating, with no conversation in it -- tool activity is names and counts, never
an input or a result.
A `.zip` is the old form, holding an event log and a copy of the whole
transcript; those archives exist on other machines and some were already sent,
so they are still read rather than abandoned -- but only for what a document
also carries, so the columns line up.

Nothing here imports the plugins' `agent_telemetry` package. The file on disk is
the interface between the two sides.

Two rules survive from reading the old transcripts and still matter, because a
v1 archive is read with them: Claude Code repeats a message's whole `usage` on
every content-block record, so usage is summed one per `message.id`; and cost
comes from the largest `cost-state`, never the last, with absence meaning
unknown rather than zero. The current plugin applies both before writing a
document, so a `.json` row simply sums what it is given.

A stored `scale` is the authority for reading its own `value`. `fom` is free
text in whatever unit that session used, so it does not compare across sessions;
`satisfaction` is the 1-5 normalisation that does.
"""

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
# Blank rather than zero wherever tool activity was not collected: a document
# written before schema 3, or an archive. "Ran no tools" is a different claim.
TOOL_FIELDS = ("tools", "tool_calls", "tool_names", "skill_calls", "skills_used")
FEEDBACK_FIELDS = (
    "subject", "fom", "value", "unit", "better", "scale",
    "satisfaction", "comment", "legacy_scale",
)


def sessions(directory=None):
    """One row per result file in `directory`, oldest session first."""
    rows = [read(path) for path in result_paths(directory)]
    return sorted((row for row in rows if row), key=lambda row: row["started"] or "")


def telemetry_dir():
    return os.environ.get(TELEMETRY_DIR_ENV) or os.path.join(
        os.path.expanduser("~"), DEFAULT_DIR_NAME
    )


def result_paths(directory=None):
    directory = directory or telemetry_dir()
    if not os.path.isdir(directory):
        return []
    names = sorted(n for n in os.listdir(directory) if n.endswith((".json", ".zip")))
    return [os.path.join(directory, name) for name in names]


def read(path):
    """Flatten one result file into a row, whichever format it is in."""
    reader = _read_archive if path.endswith(".zip") else _read_document
    try:
        return reader(path)
    except Exception:
        return None


# --- the current form: one JSON document -------------------------------------


def _read_document(path):
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    session = doc.get("session") or {}
    host = session.get("host") or {}
    row = {
        "result": os.path.basename(path),
        "format": doc.get("schema_version", 2),
        "agent": session.get("agent"),
        "session_id": session.get("session_id"),
        "user": host.get("user"),
        "email": host.get("email"),
        "os": host.get("os"),
        "cwd": session.get("cwd"),
        "started": session.get("started"),
        "ended": session.get("ended"),
        "duration_s": _elapsed(session.get("started"), session.get("ended")),
        "skills": len(doc.get("skills") or []),
        "skills_with_text": sum(
            1 for skill in doc.get("skills") or [] if skill.get("source") != "listing"
        ),
        "skill_names": ", ".join(sorted(s.get("name", "") for s in doc.get("skills") or [])),
        "context_files": len(doc.get("context") or []),
        "context_chars": sum(len(c.get("text") or "") for c in doc.get("context") or []),
    }
    row.update(_tool_activity(doc))
    row.update(_totals(doc.get("usage") or [], doc.get("cost_usd")))
    row.update(_feedback(doc.get("feedback")))
    return row


def _tool_activity(doc):
    """Which tools ran and how often, and which of the skills were used."""
    if "tools" not in doc:
        return dict.fromkeys(TOOL_FIELDS)
    ran = doc.get("tools") or []
    used = [skill for skill in doc.get("skills") or [] if skill.get("uses")]
    used.sort(key=lambda skill: (-skill["uses"], skill.get("name") or ""))
    return {
        "tools": len(ran),
        "tool_calls": sum(tool.get("calls") or 0 for tool in ran),
        "tool_names": _counted(ran, "name", "calls"),
        "skill_calls": sum(skill["uses"] for skill in used),
        "skills_used": _counted(used, "name", "uses"),
    }


def _counted(entries, name, count):
    return ", ".join(f"{entry.get(name)} {entry.get(count)}" for entry in entries)


# --- the old form: a zip of an event log and a transcript --------------------


def _read_archive(path):
    with zipfile.ZipFile(path) as archive:
        events = _members(archive, EVENTS_MEMBER)
        transcript = _members(archive, TRANSCRIPT_MEMBER)
    first, last = (events[0], events[-1]) if events else ({}, {})
    host = first.get("host") or {}
    row = {
        "result": os.path.basename(path),
        "format": 1,
        "agent": first.get("agent"),
        "session_id": first.get("session_id"),
        "user": host.get("user"),
        "email": host.get("email"),
        "os": host.get("os"),
        "cwd": first.get("cwd"),
        "started": first.get("timestamp"),
        "ended": last.get("timestamp"),
        "duration_s": _elapsed(first.get("timestamp"), last.get("timestamp")),
        # A v1 archive predates skill and context collection entirely. It has a
        # whole transcript and still cannot answer these, which is the point.
        "skills": None,
        "skills_with_text": None,
        "skill_names": None,
        "context_files": None,
        "context_chars": None,
    }
    row.update(dict.fromkeys(TOOL_FIELDS))
    rows, cost = _v1_usage(first.get("agent"), transcript)
    row.update(_totals(rows, cost))
    row.update(_feedback(_v1_feedback(events)))
    return row


def _members(archive, name):
    if name not in archive.namelist():
        return []
    lines = archive.read(name).decode("utf-8", "replace").splitlines()
    return [record for record in map(_parse, lines) if record is not None]


def _parse(line):
    try:
        return json.loads(line)
    except ValueError:
        return None


def _v1_usage(agent, transcript):
    if agent == "claude-code":
        return _v1_claude(transcript)
    if agent == "opencode":
        return _v1_opencode(transcript)
    return [], None


def _v1_claude(transcript):
    """One usage per `message.id`; a record per content block repeats it."""
    rows, costs, seen = [], [], set()
    for record in transcript:
        if record.get("type") == "assistant":
            message = record.get("message") or {}
            if message.get("id") in seen:
                continue
            seen.add(message.get("id"))
            usage = message.get("usage") or {}
            details = usage.get("output_tokens_details") or {}
            rows.append({
                "model": message.get("model"),
                "input": usage.get("input_tokens") or 0,
                "output": usage.get("output_tokens") or 0,
                "reasoning": details.get("thinking_tokens") or 0,
                "cache_read": usage.get("cache_read_input_tokens") or 0,
                "cache_write": usage.get("cache_creation_input_tokens") or 0,
            })
        elif record.get("type") == "cost-state" and record.get("totalCostUSD") is not None:
            costs.append(record["totalCostUSD"])
    return rows, (max(costs) if costs else None)


def _v1_opencode(transcript):
    rows, cost, any_reply = [], 0.0, False
    for record in transcript:
        info = record.get("info") or {}
        if info.get("role") != "assistant":
            continue
        any_reply = True
        cost += info.get("cost") or 0
        tokens = info.get("tokens") or {}
        cache = tokens.get("cache") or {}
        rows.append({
            "model": "/".join(p for p in (info.get("providerID"), info.get("modelID")) if p),
            "input": tokens.get("input") or 0,
            "output": tokens.get("output") or 0,
            "reasoning": tokens.get("reasoning") or 0,
            "cache_read": cache.get("read") or 0,
            "cache_write": cache.get("write") or 0,
        })
    return rows, (cost if any_reply else None)


def _v1_feedback(events):
    rated = [event for event in events if event.get("event_type") == "feedback"]
    return rated[-1] if rated else None


# --- shared ------------------------------------------------------------------


def _totals(rows, cost):
    totals = {field: 0 for field in TOKEN_FIELDS}
    for row in rows:
        for field in TOKEN_FIELDS:
            totals[field] += row.get(field) or 0
    totals["messages"] = len(rows)
    totals["total"] = sum(totals[field] for field in BILLED_FIELDS)
    totals["cost_usd"] = cost
    totals["models"] = ", ".join(dict.fromkeys(r.get("model") for r in rows if r.get("model")))
    return totals


def _feedback(answer):
    """The session's rating, read through the scale it was written against."""
    if not answer:
        return dict.fromkeys(FEEDBACK_FIELDS)
    scale = answer.get("scale") or {}
    fields = {
        name: answer.get(name)
        for name in ("subject", "fom", "value", "satisfaction", "comment")
    }
    return fields | {
        "unit": scale.get("unit"),
        "better": scale.get("better"),
        "scale": describe_scale(scale),
        # Ratings from before measured figures existed carry a 1-5 scale
        # whatever the figure, so their value is not a measurement.
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


def _elapsed(start, end):
    import datetime as _dt

    def moment(stamp):
        try:
            return _dt.datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            return None

    start, end = moment(start), moment(end)
    return round((end - start).total_seconds(), 1) if start and end else None
