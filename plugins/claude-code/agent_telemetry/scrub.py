"""Rewriting local paths out of a document on its way out.

A result is meant to sit next to other people's, so the layout of the machine it
was collected on is neither interesting nor ours to hand over. Every string in
the document is rewritten, texts included: the session's own directory becomes
`$PROJECTS/<name>`, so two checkouts of one project read alike, and anything
else under the home directory becomes `$HOME/...`.

`session.cwd` is the directory's name on its own and needs no prefix, so it is
already trimmed by the time this runs.
"""

import os

PROJECTS = "$PROJECTS"
HOME = "$HOME"


def document(doc, cwd):
    """`doc` with every local path rewritten. Its structure is untouched."""
    return _walk(doc, _prefixes(cwd))


def _prefixes(cwd):
    """`[(path, name)]`, longest first, so the project wins over the home it is in."""
    found = [_prefix(cwd, lambda d: f"{PROJECTS}/{os.path.basename(d)}")]
    found.append(_prefix(os.path.expanduser("~"), lambda _: HOME))
    return sorted((pair for pair in found if pair), key=lambda pair: -len(pair[0]))


def _prefix(directory, name):
    if not directory:
        return None
    directory = os.path.normpath(directory)
    return None if directory == os.sep else (directory, name(directory))


def _walk(value, prefixes):
    if isinstance(value, dict):
        return {key: _walk(item, prefixes) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item, prefixes) for item in value]
    if isinstance(value, str):
        return _rewritten(value, prefixes)
    return value


def _rewritten(text, prefixes):
    for directory, name in prefixes:
        text = text.replace(directory, name)
    return text
