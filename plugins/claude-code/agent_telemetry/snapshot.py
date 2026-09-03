"""Session transcript snapshots.

The Claude Code transcript at ``transcript_path`` carries assistant output,
token usage and cost, none of which appear in any hook payload. Snapshots copy
it next to the telemetry log so the data outlives Claude Code's own retention of
``~/.claude/projects``. Like every write in this package, a snapshot is
best-effort and never interrupts a session.
"""

import json
import os
import shutil
import sys
import tempfile

from . import writer

TRANSCRIPT_DIR_ENV = "AGENT_TELEMETRY_TRANSCRIPT_DIR"
DEFAULT_DIR_NAME = "agent-telemetry-transcripts"


def transcript_dir():
    configured = os.environ.get(TRANSCRIPT_DIR_ENV)
    if configured:
        return configured
    log = writer.log_path()
    return os.path.join(os.path.dirname(log), DEFAULT_DIR_NAME) if log else None


def snapshot(transcript_path, session_id=None):
    """Copy one transcript into the snapshot directory. Returns the destination."""
    try:
        return _copy(transcript_path, session_id)
    except Exception:
        return None


def _copy(transcript_path, session_id):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    destination = _destination(transcript_path, session_id)
    if not destination:
        return None
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    _replace_atomically(transcript_path, destination)
    return destination


def _destination(transcript_path, session_id):
    directory = transcript_dir()
    if not directory:
        return None
    name = session_id or _stem(transcript_path)
    return os.path.join(directory, name + ".jsonl")


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def _replace_atomically(source, destination):
    """Stage beside the destination so a failed copy never truncates a snapshot."""
    handle, staged = tempfile.mkstemp(dir=os.path.dirname(destination), suffix=".part")
    os.close(handle)
    try:
        shutil.copyfile(source, staged)
        os.replace(staged, destination)
    except Exception:
        _remove(staged)
        raise


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
    log = writer.log_path()
    if not log or not os.path.isfile(log):
        return set()
    with open(log, encoding="utf-8") as handle:
        return {p for p in _transcript_paths(handle, cwd) if p}


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
    destination = snapshot(transcript)
    print(f"snapshot -> {destination}" if destination else f"snapshot failed: {transcript}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
