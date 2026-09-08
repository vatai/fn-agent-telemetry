"""Telemetry for local Claude Code and opencode CLI sessions.

Collects six things per rated session and nothing else: the skills that were
available and their defining text, per-message token usage, the session cost,
the `AGENTS.md` and `CLAUDE.md` instructions in effect, which tools ran and how
often, and the user's rating. Tool activity is names and counts; no tool input
or result is collected, no conversation, and no transcript is kept.
"""

SCHEMA_VERSION = 3
