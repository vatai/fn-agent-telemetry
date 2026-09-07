"""Telemetry for local Claude Code and opencode CLI sessions.

Collects five things per rated session and nothing else: the skills that were
available and their defining text, per-message token usage, the session cost,
the `AGENTS.md` and `CLAUDE.md` instructions in effect, and the user's rating.
No conversation is collected and no transcript is kept.
"""

SCHEMA_VERSION = 2
