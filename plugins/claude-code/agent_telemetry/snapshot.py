"""Per-session telemetry archives.

A snapshot packs one session's hook events and its transcript into
`<AGENT_TELEMETRY_DIR>/<date>-<time>-<session_id>.zip`. The transcript is where
assistant output, token usage and cost live -- none of them reach a hook payload
-- and archiving it also outlives the agent's own retention of the conversation.
Like every write in this package, a snapshot is best-effort and never interrupts
a session.

Nothing here runs on its own. Archiving happens only as the last step of the
`/fn-eval` command, so a session nobody rates leaves no archive at all.
"""

import datetime as _dt
import os
import tempfile
import zipfile

from . import events, paths


def snapshot(session_id, transcript_path):
    """Archive one session. Returns the archive path, or None if nothing was written."""
    try:
        return _archive(session_id, transcript_path)
    except Exception:
        return None


def resolve_session(cwd, agent):
    """The session `/fn-eval` was typed in, and the transcript it recorded.

    A slash command receives no session id, so the session is recovered from the
    events its own hooks already logged: of the logs holding an event for this
    agent in this directory, the most recently written one is the caller's.
    """
    for log in _logs_by_recency():
        session_id, transcript_path = _last_event_in(log, cwd, agent)
        if session_id:
            return session_id, transcript_path
    return None, None


def _archive(session_id, transcript_path):
    destination = paths.archive_path(session_id, _session_started(session_id))
    members = _members(session_id, transcript_path)
    if not destination or not members:
        return None
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    _write_archive(destination, members)
    return destination


def _members(session_id, transcript_path):
    """Map archive member name to source file, skipping whatever does not exist."""
    sources = {
        paths.EVENTS_MEMBER: paths.log_path(session_id),
        paths.TRANSCRIPT_MEMBER: transcript_path,
    }
    return {name: path for name, path in sources.items() if path and os.path.isfile(path)}


def _write_archive(destination, members):
    """Stage beside the destination so a failed write never truncates an archive."""
    staged = _stage(destination)
    try:
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, source in sorted(members.items()):
                archive.write(source, name)
        os.replace(staged, destination)
    except Exception:
        _remove(staged)
        raise


def _stage(destination):
    handle, staged = tempfile.mkstemp(dir=os.path.dirname(destination), suffix=".part")
    os.close(handle)
    return staged


def _session_started(session_id):
    """When the session's first event was recorded, in local time.

    The archive is named for this rather than for the moment it is packed, so
    repacking a session overwrites one archive instead of leaving a trail of
    near-identical zips. Events store UTC; the name is local because it is read
    by whoever is browsing the directory.
    """
    log = paths.log_path(session_id)
    first = next(events.read_log(log), {}) if log and os.path.isfile(log) else {}
    return _local_time(first.get("timestamp"))


def _local_time(timestamp):
    try:
        return _dt.datetime.fromisoformat(timestamp).astimezone()
    except (TypeError, ValueError):
        return None


def _logs_by_recency():
    directory = paths.pending_dir()
    if not directory or not os.path.isdir(directory):
        return []
    logs = [os.path.join(directory, n) for n in os.listdir(directory) if paths.is_log(n)]
    return sorted(logs, key=os.path.getmtime, reverse=True)


def _last_event_in(log, cwd, agent):
    """Session id and transcript path of the last event in `log` from this caller."""
    found = (None, None)
    for event in events.read_log(log):
        if event.get("cwd") == cwd and event.get("agent") == agent:
            found = (event.get("session_id"), event.get("transcript_path"))
    return found


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
