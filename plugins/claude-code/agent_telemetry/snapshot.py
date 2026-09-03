"""Per-session telemetry archives.

A snapshot packs one session's hook events and its Claude Code transcript into
`<AGENT_TELEMETRY_DIR>/<session_id>.zip`. The transcript is where assistant
output, token usage and cost live -- none of them reach a hook payload -- and
archiving it also outlives Claude Code's own retention of ``~/.claude/projects``.
Like every write in this package, a snapshot is best-effort and never interrupts
a session.
"""

import json
import os
import sys
import tempfile
import zipfile

from . import paths


def snapshot(transcript_path, session_id=None):
    """Archive one session. Returns the archive path, or None if nothing was written."""
    try:
        return _archive(transcript_path, session_id)
    except Exception:
        return None


def _archive(transcript_path, session_id):
    session = session_id or _stem(transcript_path)
    destination = paths.archive_path(session)
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


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0] if path else None


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def resolve_transcript(cwd):
    """Newest transcript recorded for ``cwd``, for the manual snapshot command.

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
    names = sorted(n for n in os.listdir(directory) if n.endswith(".jsonl"))
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


def main(argv=None):
    """Entry point for the manual `/snapshot` command. Prints one status line."""
    argv = sys.argv[1:] if argv is None else argv
    cwd = argv[0] if argv else os.getcwd()
    transcript = resolve_transcript(cwd)
    if not transcript:
        print(f"no transcript recorded for {cwd}")
        return 0
    archive = snapshot(transcript)
    print(f"snapshot -> {archive}" if archive else f"snapshot failed: {transcript}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
