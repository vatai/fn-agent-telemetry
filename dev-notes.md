# Dev Notes

## Rating a session: `/fn-eval`

Hooks record events from then on, with nothing to run. To archive a session, run
this once before you leave it:

```
/fn-eval
```

The agent proposes what the session should be judged on, then asks three
questions, one at a time, and packs the archive.

| Question | Asks for                                    | You answer             |
| -------- | ------------------------------------------- | ---------------------- |
| Q1       | the figure of merit — what was measured     | a name, or your own    |
| Q2       | its value                                   | a number, in Q1's unit |
| Q3       | the session overall, that figure normalised | 1–5                    |

Q1 is free text. A useful figure of merit is domain-specific — GFLOP/s for a
kernel, samples/s for a training loop, × for an optimisation — so the eight the
command offers are suggestions, not a vocabulary, and a name typed instead of
picked is stored as given. The unit comes with the number rather than from a
lookup, and the figure's scale is written onto the event as open-ended and
without a direction: `loss` falls where `accuracy` rises, and nothing can tell
which a name nobody declared in advance is.

Which is why Q3 exists. Free text alone would leave N sessions with N
incomparable metrics, so Q3 asks for the same figure normalised onto one 1–5
scale on every session: a 100× speedup is a 5, no change a 3, a slowdown a 1.
Direction lives there too, and is asked for rather than inferred. Q2 is
therefore bounded only below, while Q3 is validated properly — it is the one
field that compares across sessions and users.

Each question is worded from the answer before it, which is why they are asked
separately. Claude Code asks all three as `AskUserQuestion` menus. opencode has
no such tool, so it asks them in prose and the answers arrive as free text; the
numbers are checked in Python either way, and an answer it rejects makes the
command re-ask.

### Where the Q1 suggestions live

The suggestion list is written out in four places, because a markdown prompt
cannot import Python and each agent reads its own prompt. Add a figure to all of
them, or the agents offer different things:

| File                                              | What                                                                                                                    |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `plugins/claude-code/agent_telemetry/feedback.py` | `SUGGESTED_FOMS` — the canonical list: name, unit, what it suits. Only `--help` reads it; nothing validates against it. |
| `plugins/claude-code/commands/fn-eval.md`         | The step 2 table, offered as `AskUserQuestion` options.                                                                 |
| `plugins/opencode/command/fn-eval.md`             | The step 2 table, offered in prose.                                                                                     |
| `README.md`, `## FOM: Figure of merit`            | The user-facing prose version, and where the list came from.                                                            |

Nothing enforces agreement between them, since `--fom` accepts any name — a
list that has drifted produces valid but unevenly-prompted data, not an error.

**Skip `/fn-eval` and you get no archive.** Rating is the only thing that
creates one. The events survive in `.pending/`, but under Claude Code the
transcript — and with it the token counts and cost — is gone once Claude Code
prunes `~/.claude/projects`.

**Then close the session — Claude Code only.** `/fn-eval` packs the archive from
inside the turn it runs in, and Claude Code writes the session's cost only as
the session ends, in a `cost-state` record that is the transcript's last line.
So the `SessionEnd` hook repacks a session that has already been rated. Rate and
never exit, and the archive keeps everything but the cost. opencode has no
equivalent gap: it repacks a rated session at the end of every turn.

Q3's 1–5 scale is what keeps scores comparable across sessions and users, so it
is fixed; Q1 is deliberately not. Anything the three numbers cannot express goes
in `--comment`.

## Options

Both plugins need `python3` on `PATH`, and both read the same one setting:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
```

Append-only telemetry capture for local Claude Code and opencode CLI sessions.
One zip archive per rated session, holding that session's event log, its
transcript, and the user's own rating of how the session went. Best-effort — it
never interrupts a session.

One plugin per agent, one archive format for both. Everything below the adapter
is shared — the same Python package, the same event taxonomy, the same
`AGENT_TELEMETRY_DIR` — so both agents' sessions land side by side in one
directory, and the `agent` field on every event says which one produced it.

## Uploading

Each run of `/fn-eval`, under either agent, leaves one file to send, in
`~/agent-telemetry` (or `$AGENT_TELEMETRY_DIR`):

```
20260904-164832-610153d8-b1f9-48dc-b2e6-43b8febca643.zip
└──────┬──────┘ └────────────────┬───────────────────┘
  when the session               the agent's
  started, local time            session id
```

One per session, `<date>-<time>-<session_id>.zip` — `YYYYMMDD-HHMMSS`, so a
listing is already in chronological order and the name is unique across users
and machines. Re-running `/fn-eval` overwrites the session's own file rather
than adding another, so the whole directory is always the complete set.

_TODO: where to send them._

## Output layout

```
~/agent-telemetry/
├── 20260904-164832-<session_id>.zip    # <date>-<time>-<session_id>
│   ├── events.jsonl                   # events, plus the user's rating
│   └── transcript.jsonl               # the session's messages
└── .pending/<session_id>.jsonl        # live event log, folded in at each snapshot
```

`AGENT_TELEMETRY_DIR` is the only setting. Hooks no-op silently only when no
home directory can be resolved.

One archive per session, named for when the session _started_, in local time —
so listings sort chronologically and re-running `/fn-eval` overwrites the
archive instead of adding a near-identical one. Timestamps _inside_ are UTC.

A zip cannot be appended to and events arrive one at a time, so they accumulate
in `.pending/` and the archive is rewritten whole each time. It is staged and
renamed into place, so an interrupted run never damages the previous archive. A
session with no transcript yet is archived with `events.jsonl` alone.

Rewritten at least twice, in the ordinary case: once by `/fn-eval`, and once
after it. For Claude Code that second pass is the `SessionEnd` hook, and it is
what picks up the tail of the transcript — the rating turn itself, and the
`cost-state` line. For opencode it is the end of every subsequent turn. Either
way, a session that was never rated is not packed at any point.

## Event log format

`events.jsonl` is append-only, one JSON object per line, retained indefinitely.
Every object has:

| Field             | Description                                                                                               |
| ----------------- | --------------------------------------------------------------------------------------------------------- |
| `schema_version`  | Event schema version (currently `1`).                                                                     |
| `event_id`        | Unique UUID for this event.                                                                               |
| `timestamp`       | ISO-8601 UTC time the event was recorded.                                                                 |
| `agent`           | Source agent — `claude-code` or `opencode`.                                                               |
| `host`            | `{hostname, pid, user}` of the process that emitted the event.                                            |
| `event_type`      | Normalized type shared across agents (see below).                                                         |
| `native_event`    | The agent's own hook or bus event name — `PreToolUse`, `tool.execute.before`.                             |
| `session_id`      | The agent's session id.                                                                                   |
| `cwd`             | Session working directory. No opencode payload carries one, so the plugin's `directory` stands in.        |
| `transcript_path` | Path to the session transcript, when provided.                                                            |
| `raw`             | The unmodified native hook payload. For opencode, the payload the plugin assembled, native fields intact. |

Plus, per `event_type`. One taxonomy, two sets of native names; a `—` in an
agent's column means that agent has no such event:

| `event_type`     | Claude Code        | opencode              | Extra fields                                                                        |
| ---------------- | ------------------ | --------------------- | ----------------------------------------------------------------------------------- |
| `session_start`  | `SessionStart`     | `session.created`     | `source` (Claude Code)                                                              |
| `session_end`    | `SessionEnd`       | `session.deleted`     | `reason` (Claude Code)                                                              |
| `user_prompt`    | `UserPromptSubmit` | `chat.message`        | `prompt`                                                                            |
| `tool_pre`       | `PreToolUse`       | `tool.execute.before` | `tool_name`, `tool_input`                                                           |
| `tool_post`      | `PostToolUse`      | `tool.execute.after`  | `tool_name`, `tool_input`, `tool_response`                                          |
| `turn_end`       | `Stop`             | `session.idle`        | —                                                                                   |
| `subagent_end`   | `SubagentStop`     | —                     | —                                                                                   |
| `notification`   | `Notification`     | `session.error`       | `message`                                                                           |
| `compact`        | `PreCompact`       | `session.compacted`   | `trigger`, `custom_instructions` (Claude Code)                                      |
| `permission_ask` | —                  | `permission.ask`      | `tool_name`, `message`, `status`                                                    |
| `feedback`       | `SlashCommand`     | `SlashCommand`        | `subject`, `fom`, `scale`, `value`, `satisfaction`, `satisfaction_scale`, `comment` |

`permission_ask` is opencode-only, and is kept because how often a session had
to stop and ask is a signal nothing else carries. `subagent_end` is Claude
Code-only — opencode subagents run as sessions of their own, with a `parentID`.

Every row but `feedback` comes from a hook; `feedback` is written by `/fn-eval`.
It shares the session's `session_id` with every other event, so usage and rating
need no join. If stdin cannot be parsed as JSON it is kept verbatim under
`raw._unparsed_stdin` with `event_type` `unknown`.

A `turn_end` line:

```json
{
  "schema_version": 1,
  "event_id": "a583fb72-…",
  "timestamp": "2026-09-03T23:32:39.127497+00:00",
  "agent": "claude-code",
  "host": { "hostname": "niku", "pid": 8848, "user": "vatai" },
  "event_type": "turn_end",
  "native_event": "Stop",
  "session_id": "610153d8-…",
  "cwd": "/home/vatai/code/fn-agent-telemetry",
  "transcript_path": "/home/vatai/.claude/projects/-home-vatai-code-fn-agent-telemetry/610153d8-….jsonl",
  "raw": {
    "session_id": "610153d8-…",
    "transcript_path": "…",
    "cwd": "…",
    "hook_event_name": "Stop",
    "stop_hook_active": false
  }
}
```

## Transcript format

`transcript.jsonl` holds the session's own messages in the agent's own shape,
not this plugin's. Both shapes are undocumented upstream and do change between
releases; the below is a guide, not a contract.

### Claude Code transcripts

A verbatim copy of Claude Code's own transcript file. Observed on **v2.x,
September 2026**.

One JSON object per line, discriminated by `type`. Conversation records
(`assistant`, `user`, `system`, `attachment`) share an envelope of `uuid`,
`parentUuid`, `sessionId`, `timestamp`, `cwd`, `gitBranch`, `version`,
`isSidechain` and `userType`; session-state records carry only `sessionId`.

| `type`                                                                                | Holds                                                                             |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `assistant`                                                                           | `message` with `model`, `usage`, `stop_reason`, and `requestId`                   |
| `user`                                                                                | `message`; tool results also carry `toolUseResult`                                |
| `attachment`                                                                          | Injected context — `total_tokens_reminder`, `edited_text_file`, `skill_listing` … |
| `system`                                                                              | `subtype`: `turn_duration`, `stop_hook_summary`, `away_summary`                   |
| `cost-state`                                                                          | `totalCostUSD`, `modelUsage` per model, `totalDuration`, `totalLinesAdded`        |
| `file-history-snapshot`                                                               | `snapshot` of files touched, keyed by `messageId`                                 |
| `queue-operation`, `mode`, `permission-mode`, `last-prompt`, `ai-title`, `atis-latch` | UI and session state                                                              |

`message.content` is a list of parts: `text`, `thinking`, `tool_use`,
`server_tool_use` on `assistant`; `text` and `tool_result` on `user`.

#### Token usage and cost

Neither reaches a hook payload — the transcript is the only place they appear.

Per assistant message, `message.usage`:

```json
{
  "input_tokens": 2,
  "cache_creation_input_tokens": 974,
  "cache_read_input_tokens": 129339,
  "output_tokens": 452,
  "output_tokens_details": { "thinking_tokens": 276 },
  "server_tool_use": { "web_search_requests": 0, "web_fetch_requests": 0 },
  "service_tier": "standard"
}
```

Cumulative, in `cost-state`:

```json
{
  "type": "cost-state",
  "totalCostUSD": 5.50866775,
  "totalAPIDuration": 620673,
  "modelUsage": {
    "claude-opus-5": {
      "inputTokens": 307022,
      "outputTokens": 39713,
      "thinkingTokens": 8802,
      "cacheReadInputTokens": 3457724,
      "cacheCreationInputTokens": 126957,
      "webSearchRequests": 0,
      "costUSD": 5.5077257500000005
    }
  }
}
```

`cost-state` is written as a session ends, and is the transcript's last line
when it appears at all. A session resumed after that goes on appending, which is
why one 1716-line transcript carries its two records at lines 249 and 251 — so
take the largest rather than the last, and treat absence as _unknown_, never as
zero. Nothing writes cost mid-session: an archive packed by `/fn-eval` alone
never holds one, which is what the `SessionEnd` repack is for.

Tokens come from `message.usage`, but **sum one usage per `message.id`, not one
per `assistant` line.** A message is written out one line per content block —
`thinking` and `text` land on separate lines with separate `uuid`s — and each
carries the _whole_ message's usage, not its own share. Summing per line
double-counts exactly the messages that thought or called a tool.

### opencode transcripts

One opencode message per line, exactly as `GET /session/{id}/message` returned
it: `{"info": …, "parts": […]}`. `info` carries the role, the model, and for
assistant messages the `tokens` and `cost` of that message; `parts` carries the
text, reasoning and tool calls. Observed on **v1.18**.

Cost therefore behaves unlike Claude Code's: it is per message and present all
along, and a `0` is a real zero rather than a missing record.

## How the two plugins differ

Everything below the adapter is shared. These five things are not.

**Hooks are a module, not a subprocess.** Claude Code declares nine hooks in
`hooks.json` and runs an executable per event. opencode loads
`plugins/opencode/plugin/agent-telemetry.js` into its own process and calls
exported functions, so the plugin is what spawns the shared Python — passing the
same JSON on stdin, so the two agents' capture paths converge immediately.

**There is no transcript file for opencode.** It keeps its messages in a
database. The plugin reads them back over the SDK at the end of every turn and
dumps them to `.pending/<session_id>.transcript.jsonl`, which is the path the
adapter reports as `transcript_path`. That dump also repacks a session that has
already been rated, because `/fn-eval` packs its archive in the middle of the
turn it runs in — without the repack, the archive would miss that last turn.

**The opencode command ships inside the plugin.** A Claude Code plugin declares
its commands as files and the installer places them. Nothing places a file for
an opencode plugin installed from npm or a tarball, so the `config` hook
registers `/fn-eval` from `command/fn-eval.md` at load time — description read
from the frontmatter, body used as the template. An `fn-eval` the user has
defined themselves is left alone.

**There is no `${CLAUDE_PLUGIN_ROOT}` under opencode.** The plugin's `shell.env`
hook exports `AGENT_TELEMETRY_BIN` into the shell tool's environment, and
`/fn-eval` resolves the feedback executable through it.

**There is no `AskUserQuestion` under opencode.** The three questions are asked
in prose instead of as menus, so the answers arrive as free text. The numbers
are still checked in Python — Q2 as a number of 0 or more, Q3 as a whole number
from 1 to 5 — and a rejected one exits non-zero so the command re-asks. Q1 is
not checked, because any figure of merit is accepted by design.

## Reading the archives back

[`analysis/`](analysis) is the read side: `archives.py` turns each zip into one row —
session, activity counts, token usage, cost, rating — and `report.py` prints
those rows as a table, CSV or JSON. Its `fom` column is that session's own
figure and unit and does not compare across sessions; `sat` is the Q3
normalisation that does, and is empty for a row written before Q3 was asked. It imports nothing from the plugins and no
plugin install ships it; the archive is the interface between the two sides.

## Repo layout and status

[PLAN.md](PLAN.md) holds the goal, the specification, and the state of each
step. [AGENTS.md](AGENTS.md) is the brief for agents changing this repo. The
shared Python package lives at `plugins/claude-code/agent_telemetry/` and is
used by **both** plugins — the path is historical, not a scope.
