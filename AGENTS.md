# fn-agent-telemetry

Append-only telemetry capture for local Claude Code and opencode CLI sessions.
One JSON document per rated session, holding six things: the skills that were
available and their defining text, per-message token usage, the session cost,
the `AGENTS.md`/`CLAUDE.md` in effect, which tools ran and how often, and the
user's rating. Nothing else — no conversation, no tool inputs or results, no
hook payloads, no transcript.

## Canonical docs — read before changing anything

| File | Covers |
| ---- | ------ |
| `PLAN.md` | Goal, Specification, Plan/Steps. Keep the Plan/Steps section updated; never modify Goal or Specification. |
| `README.md` | User-facing: what `/fn-eval` asks, install for both agents, and what a figure of merit is. |
| `dev-notes.md` | The reference: the three questions and where their suggestions live, the document format, output layout, where each agent's skills and usage numbers come from, and what differs between the two plugins. |

Step status lives in `PLAN.md`, not here.

## Layout

The shared Python package is `plugins/claude-code/agent_telemetry/`, and **both**
plugins use it — the path is historical, not a scope. The opencode plugin
(`plugins/opencode/plugin/agent-telemetry.js`) resolves it relative to its own
file and pipes each hook to `agent_telemetry.hook` on stdin, so both agents
converge on the same capture path below the adapter. Per-agent normalization
lives in `agent_telemetry/adapters/`.

Consequence: an opencode config entry must point at the plugin *inside* its
checkout or package; a copy taken out of the tree cannot find the Python.

The read side is `analysis/` — `archives.py` turns each result into a row,
`report.py` prints them as a table, CSV or JSON. It is standalone: stdlib only,
no import from `agent_telemetry`, outside the paths `package.json` ships, so it
reaches no plugin install. The document on disk is the interface between the two
sides. It also still reads the old `.zip` archives, which exist on other
machines; their skill and context columns come out blank.

## Invariants

- **Telemetry never interrupts a session.** Best-effort, silent no-op on failure.
- **`/fn-eval` is the only thing that produces a result.** No hook does; skip
  the command and there is no output file.
- **A hook stores no payload.** It reads the session id, cwd and record path and
  discards the rest. `Stop` carries the assistant's whole reply, so keeping
  payloads is how conversation gets collected by accident.
- There is no event stream. The document accumulates at
  `.pending/<session_id>.json` and is rewritten whole, staged and renamed.
- Both agents share one `AGENT_TELEMETRY_DIR` (default `~/agent-telemetry`), so
  their results land side by side. It is the only setting.
- Results are named `<date>-<time>-<session_id>.json` for when the session
  *started*, local time; timestamps inside are UTC. Re-running `/fn-eval`
  overwrites the session's own file.
- `/fn-eval` asks three questions: the figure of merit, its value, and the
  session overall on a fixed 1–5 scale. The figure is free text, since a useful
  one is domain-specific; `SUGGESTED_FOMS` in `agent_telemetry/feedback.py` only
  seeds the prompt. Comparability across sessions and users rests entirely on
  that third answer, so its scale is the thing that must not move.
- Usage, cost, skills, tools, context and rating are all in one document, so
  nothing ever needs a join.
- Tokens and cost reach no hook payload under Claude Code, so its own record is
  *read* for them and never kept. Sum one usage per `message.id`, and take the
  largest `cost-state`, not the last.
- **Tool activity is names and counts.** `agent_telemetry/tools.py` counts calls
  per tool name from the same record, once per `tool_use` id (`callID` under
  opencode). One input field is read and one only: a `Skill` call's `skill`, so
  the skills a session *used* are known. Never widen that to another tool —
  a `SlashCommand`'s input is the command the user typed.
