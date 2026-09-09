"""Which skills a session had available, and the text that defines them.

The available set is not on disk. Each agent that has one publishes it into the
conversation instead, so the record is read for it the way it is read for usage,
and nothing of the record itself is kept:

- Claude Code injects `skill_listing` records -- the first carrying the full
  list, later ones carrying additions when a plugin is installed mid-session --
  so the names are folded across all of them.
- Codex writes a `world_state` record whose `host_skills` body is the listing it
  showed the model, naming each skill's `SKILL.md` through a table of roots.
- opencode publishes nothing, so its skills come out empty.

Whether the defining text is on disk differs just as much. Of nineteen skills
available in a measured Claude Code session, one had a file: `commands/fn-eval.md`,
from an installed plugin -- not even a `SKILL.md`. The other eighteen are built
into the CLI and have no file to read. Codex is the other way round: its listing
names a file for every skill in it. So a skill's `text` is its defining markdown
where one exists, and otherwise the one-line description the listing itself
carries, with `source` saying which of the two you have.
"""

import os
import re

from . import jsonl

LISTING_TYPE = "skill_listing"

# Codex publishes its listing as one markdown body inside the session's world
# state, which names skill files through a table of short roots.
CODEX_LISTING_KEY = "host_skills"
_CODEX_ROOT = re.compile(r"^-\s+`(\w+)`\s*=\s*`(.+)`$")
_CODEX_FILE = re.compile(r"\s*\(file:\s*(\S+?)\)$")


def from_claude_record(record_path, cwd=None):
    """`[{name, source, text}]` for every skill a Claude Code session had."""
    return _collected(_claude_listing(record_path), cwd)


def from_codex_record(record_path, cwd=None):
    """`[{name, source, text}]` for every skill a codex session had."""
    return _collected(_codex_listing(record_path), cwd)


def _collected(described, cwd):
    return [_skill(name, described[name], cwd) for name in sorted(described)]


def _skill(name, described, cwd):
    """One skill, with its defining file's text when a file can be found."""
    description, named = described
    path = named if named and os.path.isfile(named) else _defining_file(name, cwd)
    text = _read(path) if path else None
    if text is not None:
        return {"name": name, "source": path, "text": text}
    return {"name": name, "source": "listing", "text": description}


def _claude_listing(path):
    """Fold every `skill_listing` into one name -> (description, file) mapping.

    `names` is the authority for which skills existed; `content` is every
    description concatenated, and is parsed for per-skill text rather than
    stored, since storing it would put the entire listing in the document. No
    file is named, so each one is looked for in the layouts that hold them.
    """
    found = {}
    for record in jsonl.records(path):
        listing = record.get("attachment") or {}
        if listing.get("type") != LISTING_TYPE:
            continue
        described = _descriptions(listing.get("content") or "")
        for name in listing.get("names") or []:
            found.setdefault(name, (described.get(name), None))
    return found


def _codex_listing(path):
    """Fold every `host_skills` body into one name -> (description, file) mapping.

    Every body observed was the whole list rather than additions, so a later one
    is the better answer for a skill it mentions -- and the union is kept
    deliberately, so that a skill dropped from a later body still counts as one
    the session had available. Codex shortens descriptions, and omits skills
    entirely from a large enough set, so this is what the session was told it
    had rather than what was installed.
    """
    found = {}
    for body in _codex_bodies(path):
        roots = _codex_roots(body)
        for line in body.splitlines():
            entry = _codex_entry(line, roots)
            if entry:
                found[entry[0]] = entry[1]
    return found


def _codex_bodies(path):
    for record in jsonl.records(path):
        if record.get("type") != "world_state":
            continue
        state = (record.get("payload") or {}).get("state") or {}
        listing = state.get(CODEX_LISTING_KEY)
        body = listing.get("body") if isinstance(listing, dict) else None
        if body:
            yield body


def _codex_roots(body):
    """The `` `r0` = `/path` `` table a listing's file references are relative to."""
    roots = {}
    for line in body.splitlines():
        match = _CODEX_ROOT.match(line.strip())
        if match:
            roots[match.group(1)] = match.group(2)
    return roots


def _codex_entry(line, roots):
    """`- name: description (file: r0/name/SKILL.md)`, as the listing writes it."""
    line = line.strip()
    if not line.startswith("- ") or ": " not in line:
        return None
    name, description = line[2:].split(": ", 1)
    file, description = _codex_file(description, roots)
    return name.strip(), (description.strip() or None, file)


def _codex_file(description, roots):
    """Split the trailing file reference off a description and expand its root."""
    match = _CODEX_FILE.search(description)
    if not match:
        return None, description
    root, _, rest = match.group(1).partition("/")
    directory = roots.get(root)
    file = os.path.join(directory, rest) if directory and rest else None
    return file, description[: match.start()]


def _descriptions(content):
    """`- name: description` lines, as a Claude Code listing writes them."""
    described = {}
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("- ") or ": " not in line:
            continue
        name, description = line[2:].split(": ", 1)
        described[name.strip()] = description.strip()
    return described


def _defining_file(name, cwd):
    """The markdown that defines a skill, if any known layout holds it.

    A plugin-qualified name prefers a file under that plugin, so two plugins
    shipping the same skill name do not shadow each other.
    """
    plugin, _, stem = name.rpartition(":")
    existing = [path for path in _candidates(stem, cwd) if os.path.isfile(path)]
    if plugin:
        owned = [path for path in existing if plugin in path]
        if owned:
            return owned[0]
    return existing[0] if existing else None


def _candidates(stem, cwd):
    for root in _roots(cwd):
        yield os.path.join(root, "skills", stem, "SKILL.md")
        yield os.path.join(root, "commands", stem + ".md")


def _roots(cwd):
    """Where a skill's own files can live: a plugin, the user, or the project."""
    home = os.path.expanduser("~")
    roots = []
    cache = os.path.join(home, ".claude", "plugins", "cache")
    for marketplace in _listdir(cache):
        for plugin in _listdir(os.path.join(cache, marketplace)):
            for version in _listdir(os.path.join(cache, marketplace, plugin)):
                roots.append(os.path.join(cache, marketplace, plugin, version))
    roots.append(os.path.join(home, ".claude"))
    if cwd:
        roots.append(os.path.join(cwd, ".claude"))
    return roots


def _listdir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None
