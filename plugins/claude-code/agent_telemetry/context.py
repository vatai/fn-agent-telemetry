"""The `AGENTS.md` and `CLAUDE.md` instructions a session ran under.

Collected whole, deliberately: they are what the agent was told to do, which is
the point of having them. Taken from the working directory, the directories above
it that an agent would also load, and the user-level directories the caller
names -- which differ per agent, so the adapters say where they are.

The two names are frequently one file -- a repo that keeps `AGENTS.md` and
symlinks `CLAUDE.md` to it is the common arrangement, and this repo is one -- so
entries are keyed by the resolved file and record every name that reached it,
rather than storing the same text twice. The key is not what is reported: a
`path` is the file as it was loaded, since where a link happens to point is a
detail of one machine's filesystem, not of the session.
"""

import os

NAMES = ("AGENTS.md", "CLAUDE.md")


def collect(cwd, user_dirs=()):
    """`[{path, names, text}]`, one entry per distinct file, outermost first."""
    found = {}
    for directory in _directories(cwd, user_dirs):
        for name in NAMES:
            candidate = os.path.join(directory, name)
            if not os.path.isfile(candidate):
                continue
            key = os.path.realpath(candidate)
            entry = found.get(key)
            if entry is None:
                text = _read(candidate)
                if text is not None:
                    found[key] = _entry(candidate, text)
            elif candidate not in entry["names"]:
                entry["names"].append(candidate)
    return list(found.values())


def _entry(candidate, text):
    """A file as it was loaded, not as a link resolves: `path` is an abspath."""
    return {"path": os.path.abspath(candidate), "names": [candidate], "text": text}


def _directories(cwd, user_dirs):
    """User level first, then every directory from the filesystem root down to `cwd`."""
    directories = list(user_dirs)
    if not cwd:
        return directories
    chain, current = [], os.path.abspath(cwd)
    while True:
        chain.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return directories + list(reversed(chain))


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None
