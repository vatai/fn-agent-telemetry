"""Per-session telemetry archives.

A snapshot packs one session's hook events and its Claude Code transcript into
`<AGENT_TELEMETRY_DIR>/<date>-<time>-<session_id>.zip`. The transcript is where
assistant output, token usage and cost live -- none of them reach a hook payload
-- and archiving it also outlives Claude Code's own retention of
``~/.claude/projects``. Like every write in this package, a snapshot is
best-effort and never interrupts a session.

Nothing here runs on its own. Archiving happens only as the last step of the
`/feedback` command, so a session nobody rates leaves no archive at all.
"""

import datetime as _dt
import json
import os
import tempfile
import zipfile

from . import paths


def snapshot(transcript_path, session_id=None):
    """Archive one session. Returns the archive path, or None if nothing was written."""
    try:
        return _archive(transcript_path, session_id)
    except Exception:
        return None


def session_id_for(transcript_path):
    """Claude Code names each transcript `<session_id>.jsonl`, so the stem is the id."""
    return _stem(transcript_path)


def _archive(transcript_path, session_id):
    session = session_id or session_id_for(transcript_path)
    destination = paths.archive_path(session, _session_started(session))
    members = _members(session, transcript_path)
    if not destination or not members:
        return None
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    _write_archive(destination, members)
    return destination


def _members(session, transcript_path):
    """Map archive member name to source file, skipping whatever does not exist."""
    sources = {
        paths.EVENTS_MEMBER: paths.log_path(session),
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


def _session_started(session):
    """When the session's first event was recorded, in local time.

    The archive is named for this rather than for the moment it is packed, so
    repacking a session overwrites one archive instead of leaving a trail of
    near-identical zips. Events store UTC; the name is local because it is read
    by whoever is browsing the directory.
    """
    log = paths.log_path(session)
    first = _first_event(log) if log and os.path.isfile(log) else {}
    return _local_time(first.get("timestamp"))


def _first_event(log):
    with open(log, encoding="utf-8") as handle:
        for line in handle:
            return _parse(line)
    return {}


def _local_time(timestamp):
    try:
        return _dt.datetime.fromisoformat(timestamp).astimezone()
    except (TypeError, ValueError):
        return None


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0] if path else None


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def resolve_transcript(cwd):
    """Newest transcript recorded for ``cwd``, for the `/feedback` command.

    Slash commands receive no session id, so the session is recovered from the
    transcript paths the hooks already logged: narrow to the session directory,
    then take the most recently written, which is the caller's own transcript.
    """
    candidates = [p for p in _recorded_transcripts(cwd) if os.path.isfile(p)]
    return max(candidates, key=os.path.getmtime) if candidates else None


def _recorded_transcripts(cwd):
    recorded = set()
    for log in _event_logs():
        with open(log, encoding="utf-8") as handle:
            recorded.update(p for p in _transcript_paths(handle, cwd) if p)
    return recorded


def _event_logs():
    directory = paths.pending_dir()
    if not directory or not os.path.isdir(directory):
        return []
    names = sorted(n for n in os.listdir(directory) if n.endswith(paths.LOG_SUFFIX))
    return [os.path.join(directory, n) for n in names]


def _transcript_paths(lines, cwd):
    for line in lines:
        event = _parse(line)
        if event.get("cwd") == cwd:
            yield event.get("transcript_path")


def _parse(line):
    try:
        return json.loads(line)
    except ValueError:
        return {}

