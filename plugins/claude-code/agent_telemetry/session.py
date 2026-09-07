"""Assembling one session's document, and writing it out once rated.

Nothing here is collected per event. A hook's only jobs are to note that the
session exists, to snapshot the instructions it is running under while they are
still the ones in force, and -- when the session ends having been rated -- to
read the agent's own record for usage, cost and the skill listing.

`/fn-eval` is still the only thing that produces output. Skip it and the
document stays in `.pending/`, holding no conversation either way.
"""

import os

from . import context, document, paths, skills, usage

# Bookkeeping, not collected data: where to find the agent's own record. Kept in
# the pending document so `/fn-eval` and the end-of-session pass can find it,
# and dropped before anything is written out, so no output names a local record.
RECORD_KEY = "_record_path"

CLAUDE = "claude-code"


def observe(agent, normalized, finalize_at_end=False):
    """Note one hook event against the session's document. Best-effort."""
    try:
        return _observe(agent, normalized, finalize_at_end)
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


def _observe(agent, normalized, finalize_at_end):
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
        doc["context"] = context.collect(doc["session"].get("cwd"))
    document.save(session_id, doc)

    if event == "session_end" and finalize_at_end and document.rated(doc):
        _finalize(session_id, agent)
    return True


def _finalize(session_id, agent):
    doc = document.load(session_id)
    if doc is None or not document.rated(doc):
        return None
    _fill(doc, agent)
    destination = paths.output_path(session_id, document.started_at(doc))
    if not destination:
        return None
    shipped = {key: value for key, value in doc.items() if key != RECORD_KEY}
    document.write(destination, shipped)
    document.save(session_id, doc)
    return destination


def _fill(doc, agent):
    """Read the agent's own record for what only it knows. Never keeps it.

    opencode has no such record to read: its plugin receives usage over the SDK
    and has already stored it, and it publishes no skill listing at all.
    """
    if agent != CLAUDE:
        return
    record = doc.get(RECORD_KEY)
    rows, cost = usage.from_claude_record(record)
    if rows:
        doc["usage"] = rows
    if cost is not None:
        doc["cost_usd"] = cost
    found = skills.collect(record, (doc.get("session") or {}).get("cwd"))
    if found:
        doc["skills"] = found


def _pending_by_recency():
    directory = paths.pending_dir()
    if not directory or not os.path.isdir(directory):
        return []
    names = [n for n in os.listdir(directory) if paths.is_pending_document(n)]
    documents = [os.path.join(directory, n) for n in names]
    return sorted(documents, key=os.path.getmtime, reverse=True)
