"""Who the session belongs to, as an email address where one can be had.

Claude Code knows the account it is signed in as, and that is the answer
whenever it is there. Nothing else does, so the fallbacks descend: the git
identity configured for the project, then the git name if no address is set,
then the OS user at the machine's name -- the one place a hostname is still
worth having, there being nothing else left to tell two users apart.

Resolved once, when the document is written out, so a session that is never
rated never has it looked up.
"""

import json
import os
import subprocess

CLAUDE = "claude-code"
CLAUDE_CONFIG = "~/.claude.json"
GIT_TIMEOUT_S = 5


def of(agent, cwd=None):
    """The user's email, or the closest stand-in that can be found. May be None."""
    sources = (
        lambda: _claude_account(agent),
        lambda: _git_config("user.email", cwd),
        lambda: _git_config("user.name", cwd),
        _user_at_host,
    )
    for source in sources:
        found = _quiet(source)
        if found:
            return found
    return None


def _claude_account(agent):
    """The signed-in account, from Claude Code's own config. Only it has one."""
    if agent != CLAUDE:
        return None
    with open(os.path.expanduser(CLAUDE_CONFIG), encoding="utf-8") as handle:
        config = json.load(handle)
    return (config.get("oauthAccount") or {}).get("emailAddress")


def _git_config(key, cwd):
    """A git setting as it reads in the project, so a per-repo identity wins."""
    directory = cwd if cwd and os.path.isdir(cwd) else None
    done = subprocess.run(
        ["git", "config", "--get", key],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )
    return done.stdout.strip() or None


def _user_at_host():
    import socket

    user = os.environ.get("USER") or os.environ.get("USERNAME")
    return f"{user}@{socket.gethostname()}" if user else None


def _quiet(source):
    try:
        return source()
    except Exception:
        return None
