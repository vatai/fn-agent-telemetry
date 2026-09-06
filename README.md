# clanker-telemetry

Append-only telemetry capture for local Claude Code and opencode CLI sessions.
One zip archive per rated session, holding that session's event log, its
transcript, and the user's rating of how the session went. Both agents share one
capture path and one output directory, so their archives land side by side.

Rating is what creates an archive: run `/fn-eval` before you leave a session, or
there is nothing to send.

## Plugins

- **[plugins/claude-code/README.md](plugins/claude-code/README.md)** — the
  Claude Code plugin, and the shared reference for both agents: install,
  `/fn-eval` and the figure-of-merit table, the event schema, the archive
  layout, and the Claude Code transcript format. Start here whichever agent you
  run.
- **[plugins/opencode/README.md](plugins/opencode/README.md)** — the opencode
  plugin. Covers only what differs — install, the five things the shared capture
  path does not cover, and opencode's own transcript shape — and defers to the
  above for everything else.

## Elsewhere in the repo

- [PLAN.md](PLAN.md) — goal, specification, and the state of each step.
- [analysis/](analysis) — the read side: `archives.py` turns each zip into a
  row, `report.py` prints them as a table, CSV or JSON.
