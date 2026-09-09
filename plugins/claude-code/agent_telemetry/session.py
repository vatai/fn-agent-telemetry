"""Assembling one session's document, and writing it out once rated.

Nothing here is collected per event. A hook's only jobs are to note that the
session exists, to snapshot the instructions it is running under while they are
still the ones in force, and -- once the session has been rated, at the events
its adapter names -- to read the agent's own record for usage, cost, tool
activity and the skill listing.

`/fn-eval` is still the only thing that produces output. Skip it and the
document stays in `.pending/`, holding no conversation either way.
"""

import os

from . import (
    SCHEMA_VERSION,
    adapters,
    context,
    document,
    identity,
    paths,
    scrub,
    skills,
    tools,
    usage,
)

# Bookkeeping, not collected data: where to find the agent's own record. Kept in
# the pending document so `/fn-eval` and the later passes can find it, and
# dropped before anything is written out, so no output names a local record.
RECORD_KEY = "_record_path"

CLAUDE = "claude-code"
CODEX = "codex"

# What each agent's own record can be read for, and how. opencode keeps no
# record to read: its plugin receives usage over the SDK and has already stored
# it, and it publishes no skill listing at all.
_RECORD_READERS = {
    CLAUDE: (usage.from_claude_record, tools.from_claude_record, skills.from_claude_record),
    CODEX: (usage.from_codex_record, tools.from_codex_record, skills.from_codex_record),
}


def observe(agent, normalized):
    """Note one hook event against the session's document. Best-effort."""
    try:
        return _observe(agent, normalized)
    except Exception:
        return False


def finalize(session_id, agent):
    """Collect what is only readable at the end, and write the document out.

    Returns the output path, or None when there was nothing to write. A session
    that carries no rating is deliberately left pending.
    """
    try:
        return _finalize(session_id, agent)
    except Exception:
        return None


def resolve(cwd, agent):
    """The session `/fn-eval` was typed in.

    A slash command receives no session id, so the session is recovered from the
    pending documents: of those for this agent in this directory, the most
    recently written is the caller's.
    """
    for path in _pending_by_recency():
        found = document.read(path) or {}
        session = found.get("session") or {}
        if session.get("cwd") == cwd and session.get("agent") == agent:
            return session.get("session_id")
    return None


def _observe(agent, normalized):
    session_id = normalized.get("session_id")
    if not session_id:
        return False
    path = paths.pending_path(session_id)
    if not path:
        return False

    event = normalized.get("event_type")
    existing = document.read(path) if os.path.isfile(path) else None
    # Every other hook is a no-op once the document exists: there is no event
    # stream to append to, so writing on each one would only rewrite the file.
    if existing is not None and event not in ("session_start", "session_end", "turn_end"):
        return False

    doc = existing or document.blank(session_id, agent)
    doc[RECORD_KEY] = normalized.get("transcript_path") or doc.get(RECORD_KEY)
    document.touch(
        doc,
        cwd=normalized.get("cwd"),
        started=event == "session_start",
        ended=event in ("session_end", "turn_end"),
    )
    if event == "session_start" or not doc.get("context"):
        doc["context"] = context.collect(doc["session"].get("cwd"), _user_instruction_dirs(agent))
    document.save(session_id, doc)

    if event in _finalize_at(agent) and document.rated(doc):
        _finalize(session_id, agent)
    return True


def _finalize(session_id, agent):
    doc = document.load(session_id)
    if doc is None or not document.rated(doc):
        return None
    _fill(doc, agent)
    _identify(doc, agent)
    # A document that has been pending since an older version was collected by
    # this one, so it is stamped for the shape it is written in, not the shape
    # it was started in.
    doc["schema_version"] = SCHEMA_VERSION
    destination = paths.output_path(session_id, document.started_at(doc))
    if not destination:
        return None
    document.write(destination, _shipped(doc))
    document.save(session_id, doc)
    return destination


def _shipped(doc):
    """The document as it is written out: no record path, and no local paths."""
    session = doc.get("session") or {}
    shipped = {key: value for key, value in doc.items() if key != RECORD_KEY}
    shipped["session"] = _shipped_session(session)
    return scrub.document(shipped, session.get("cwd"))


def _shipped_session(session):
    """Only the project directory's name goes out, not where it sits on this disk.

    The pending document keeps the whole path: `resolve` matches on it, and the
    skill and instruction lookups walk it.
    """
    cwd = session.get("cwd")
    if not cwd:
        return session
    return session | {"cwd": os.path.basename(os.path.normpath(cwd))}


def _identify(doc, agent):
    """Whose session it was. Looked up once and kept, since it cannot change."""
    session = doc.setdefault("session", {})
    host = session.setdefault("host", {})
    if not host.get("email"):
        host["email"] = identity.of(agent, session.get("cwd"))


def _finalize_at(agent):
    """The events at which this agent's rated session is worth writing out."""
    return getattr(adapters.get_adapter(agent), "FINALIZE_AT", ())


def _user_instruction_dirs(agent):
    """The user-level instruction directories this agent reads. Empty if unknown."""
    adapter = adapters.get_adapter(agent)
    return getattr(adapter, "user_instruction_dirs", list)()


def _fill(doc, agent):
    """Read the agent's own record for what only it knows. Never keeps it."""
    readers = _RECORD_READERS.get(agent)
    if readers is None:
        return
    read_usage, read_tools, read_skills = readers
    record = _record_path(doc, agent)
    rows, cost = read_usage(record)
    if rows:
        doc["usage"] = rows
    if cost is not None:
        doc["cost_usd"] = cost
    ran, invoked = read_tools(record)
    if ran:
        doc["tools"] = ran
    found = read_skills(record, (doc.get("session") or {}).get("cwd"))
    if found:
        doc["skills"] = _with_uses(found, invoked)


def _record_path(doc, agent):
    """Where the agent's record is: as its payload named it, or as it lays them out.

    Only codex needs the second: it documents `transcript_path` as not a stable
    interface, so its adapter finds the rollout by session id when the path in
    the payload is not there.
    """
    given = doc.get(RECORD_KEY)
    locate = getattr(adapters.get_adapter(agent), "locate_record", None)
    return locate(given, (doc.get("session") or {}).get("session_id")) if locate else given


def _with_uses(found, invoked):
    """How often each available skill was actually invoked.

    `invoked` is None for an agent that cannot say -- codex names the skill in
    no tool call -- and then no skill carries a `uses` at all, since a `0` there
    would claim the skill went unused rather than uncounted.

    A skill invoked but absent from the listing would otherwise be lost, so it
    is added with `invocation` as its source and no defining text.
    """
    if invoked is None:
        return found
    listed = [skill | {"uses": invoked.get(skill["name"], 0)} for skill in found]
    names = {skill["name"] for skill in found}
    unlisted = sorted(name for name in invoked if name not in names)
    return listed + [
        {"name": name, "source": "invocation", "text": None, "uses": invoked[name]}
        for name in unlisted
    ]


def _pending_by_recency():
    directory = paths.pending_dir()
    if not directory or not os.path.isdir(directory):
        return []
    names = [n for n in os.listdir(directory) if paths.is_pending_document(n)]
    documents = [os.path.join(directory, n) for n in names]
    return sorted(documents, key=os.path.getmtime, reverse=True)
