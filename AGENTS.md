# clanker-telemetry

Append-only telemetry capture for local Claude Code and opencode CLI sessions.
One zip archive per rated session, holding that session's event log, its
transcript, and the user's rating.

## Canonical docs — read before changing anything

| File | Covers |
| ---- | ------ |
| `survey-collection-plan.md` | Goal, Specification, Plan/Steps — this repo's `PLAN.md`. Keep the Plan/Steps section updated; never modify Goal or Specification. |
| `plugins/claude-code/README.md` | The shared reference: install, `/fn-eval`, figure-of-merit table, event schema, archive layout, Claude Code transcript format. |
| `plugins/opencode/README.md` | Only what differs for opencode; defers to the above for everything shared. |

Step status lives in `survey-collection-plan.md`, not here.

## Layout

The shared Python package is `plugins/claude-code/agent_telemetry/`, and **both**
plugins use it — the path is historical, not a scope. The opencode plugin
(`plugins/opencode/plugin/agent-telemetry.js`) resolves it relative to its own
file and pipes each hook to `agent_telemetry.hook` on stdin, so both agents
converge on the same capture path below the adapter. Per-agent normalization
lives in `agent_telemetry/adapters/`.

Consequence: an opencode config entry must point at the plugin *inside* its
checkout or package; a copy taken out of the tree cannot find the Python.

## Invariants

- **Telemetry never interrupts a session.** Best-effort, silent no-op on failure.
- **`/fn-eval` is the only thing that packs an archive.** No hook triggers one;
  skip the command and there is no archive.
- A zip cannot be appended to, so events pool in `.pending/<session_id>.jsonl`
  and the archive is rewritten whole, staged and renamed into place.
- Both agents share one `AGENT_TELEMETRY_DIR` (default `~/agent-telemetry`), so
  their archives land side by side. It is the only setting.
- Archives are named `<date>-<time>-<session_id>.zip` for when the session
  *started*, local time; timestamps inside are UTC. Re-running `/fn-eval`
  overwrites the session's own archive.
- The figure-of-merit vocabulary and its scales are fixed in
  `agent_telemetry/feedback.py`. Widen it *before* collecting, not after —
  scores must stay comparable across sessions and users.
- Every event carries `session_id` and `agent`, so usage and rating need no join.
