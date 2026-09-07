"""Which skills a session had available, and the text that defines them.

The available set is not on disk. Claude Code injects it into the conversation as
`skill_listing` records -- the first carrying the full list, later ones carrying
additions when a plugin is installed mid-session -- so the names are folded
across all of them. That is a read of the session record, like usage; nothing of
the record itself is kept.

The defining text mostly is not on disk either. Of nineteen skills available in a
measured session, one had a file: `commands/fn-eval.md`, from an installed plugin
-- not even a `SKILL.md`. The other eighteen are built into the CLI and have no
file to read. So a skill's `text` is its defining markdown where one exists, and
otherwise the one-line description the listing itself carries, with `source`
saying which of the two you have.
"""

import json
import os

LISTING_TYPE = "skill_listing"


def collect(record_path, cwd=None):
    """`[{name, source, text}]` for every skill the session had available."""
    described = _from_listing(record_path)
    return [_skill(name, described[name], cwd) for name in sorted(described)]


def _skill(name, description, cwd):
    path = _defining_file(name, cwd)
    text = _read(path) if path else None
    if text is not None:
        return {"name": name, "source": path, "text": text}
    return {"name": name, "source": "listing", "text": description}


def _from_listing(path):
    """Fold every `skill_listing` into one name -> description mapping.

    `names` is the authority for which skills existed; `content` is every
    description concatenated, and is parsed for per-skill text rather than
    stored, since storing it would put the entire listing in the document.
    """
    found = {}
    for record in _records(path):
        listing = record.get("attachment") or {}
        if listing.get("type") != LISTING_TYPE:
            continue
        described = _descriptions(listing.get("content") or "")
        for name in listing.get("names") or []:
            found.setdefault(name, described.get(name))
    return found


def _descriptions(content):
    """`- name: description` lines, as the listing writes them."""
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


def _records(path):
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except ValueError:
                continue
