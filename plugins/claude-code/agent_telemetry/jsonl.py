"""Reading an agent's own session record, one JSON object per line.

Three collectors read that record -- usage, skills and tool activity -- and each
one takes only the numbers or names it is after; nothing of the record itself is
ever kept. A half-written last line is normal in a file the agent is still
appending to, so an unparseable line is skipped rather than fatal.
"""

import json
import os


def records(path):
    """Yield the parsed records of a JSONL file, tolerating a half-written line."""
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except ValueError:
                continue
