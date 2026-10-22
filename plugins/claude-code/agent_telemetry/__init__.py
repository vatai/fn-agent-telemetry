"""Telemetry for local Claude Code, codex and opencode CLI sessions.

Collects six things per rated session and nothing else: the skills that were
available and their defining text, token usage totalled per model, the session
cost, the `AGENTS.md` and `CLAUDE.md` instructions in effect, which tools ran and
how often, and the user's rating with a summary of the work they approved. Tool
activity is names and counts; no tool input or result is collected, no
conversation, and no transcript is kept.
"""

SCHEMA_VERSION = 5
