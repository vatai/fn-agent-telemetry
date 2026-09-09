# fn-agent-telemetry

Append-only telemetry capture for local Claude Code, codex and opencode CLI
sessions. One JSON document per rated session, holding six things: the skills
that were available and their defining text, per-message token usage, the
session cost, the `AGENTS.md`/`CLAUDE.md` in effect, which tools ran and how
often, and the user's rating. Nothing else — no conversation, no tool inputs or
results, no hook payloads, no transcript.

## Canonical docs — read before changing anything

| File | Covers |
| ---- | ------ |
| `PLAN.md` | Goal, Specification, Plan/Steps. Keep the Plan/Steps section updated; never modify Goal or Specification. |
| `README.md` | User-facing: what `/fn-eval` asks, install for each agent, and what a figure of merit is. |
| `dev-notes.md` | The reference: the three questions and where their suggestions live, the document format, output layout, where each agent's skills and usage numbers come from, and what differs between the plugins. |

Step status lives in `PLAN.md`, not here.

## Layout

The shared Python package is `plugins/claude-code/agent_telemetry/`, and **all
three** plugins use it — the path is historical, not a scope. The opencode plugin
(`plugins/opencode/plugin/agent-telemetry.js`) resolves it relative to its own
file and pipes each hook to `agent_telemetry.hook` on stdin; the codex plugin
(`plugins/codex/bin/`) is a pair of shell wrappers that do the same, codex
running an executable per hook the way Claude Code does. So all three agents
converge on the same capture path below the adapter. Per-agent normalization
lives in `agent_telemetry/adapters/`, and each adapter's `FINALIZE_AT` names the
events at which a rated session is worth writing out again.

Consequence: an opencode config entry or a codex `hooks.json` must point at the
plugin *inside* its checkout or package; a copy taken out of the tree cannot
find the Python. Which is why codex is installed by clone and hook config rather
than as a codex plugin: a marketplace install would copy `plugins/codex/` alone.

The read side is `analysis/` — `archives.py` turns each result into a row,
`report.py` prints them as a table, CSV or JSON. It is standalone: stdlib only,
no import from `agent_telemetry`, outside the paths `package.json` ships, so it
reaches no plugin install. The document on disk is the interface between the two
sides. It also still reads the old `.zip` archives, which exist on other
machines; their skill and context columns come out blank.

`tests/` runs both sides: `tests/run`, stdlib `unittest`, no dependency beyond
`python3`. It drives the plugins the way their agents do — a wrapper with a
payload on stdin, an entry point as `python3 -m` — in a temporary `HOME` and
`AGENT_TELEMETRY_DIR`. Change what a plugin collects and the example inputs in
`tests/records.py` are where to say what the new shape looks like; `dev-notes.md`
has the file-by-file map.

## Invariants

- **Telemetry never interrupts a session.** Best-effort, silent no-op on failure.
- **`/fn-eval` is the only thing that produces a result.** No hook does; skip
  the command and there is no output file. Under codex it is a skill invoked
  `$fn-eval`, codex having deprecated custom prompts; same three questions, same
  document.
- **A hook stores no payload.** It reads the session id, cwd and record path and
  discards the rest. `Stop` carries the assistant's whole reply, so keeping
  payloads is how conversation gets collected by accident.
- There is no event stream. The document accumulates at
  `.pending/<session_id>.json` and is rewritten whole, staged and renamed.
- Every agent shares one `AGENT_TELEMETRY_DIR` (default `~/agent-telemetry`), so
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
- Codex's record is read the same way, but its counts are cumulative, so a usage
  row is what they grew by — and its `input_tokens` includes the cached tokens,
  which Claude Code's does not. Codex reports **no cost at all**; `null` there is
  the answer, not a gap to fill. Its `transcript_path` is documented as unstable,
  so the rollout is located by session id when that path is not a file.
- **Tool activity is names and counts.** `agent_telemetry/tools.py` counts calls
  per tool name from the same record, once per `tool_use` id (`callID` under
  opencode, `call_id` under codex). One input field is read and one only: a
  `Skill` call's `skill`, so the skills a session *used* are known. Never widen
  that to another tool — a `SlashCommand`'s input is the command the user typed,
  and a codex call's input is the shell command it ran. Only Claude Code has that
  field, so only its skills carry `uses`; absent is not `0`.
