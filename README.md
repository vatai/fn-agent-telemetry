# fn-agent-telemetry

Append-only telemetry capture for local Claude Code and opencode CLI sessions.
One zip archive per rated session, holding that session's event log, its
transcript, and the user's own rating of how the session went. Best-effort — it
never interrupts a session.

One plugin per agent, one archive format for both. Everything below the adapter
is shared — the same Python package, the same event taxonomy, the same
`AGENT_TELEMETRY_DIR` — so both agents' sessions land side by side in one
directory, and the `agent` field on every event says which one produced it.

## Install

Both plugins need `python3` on `PATH`, and both read the same one setting:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
```

### Claude Code

```sh
claude plugin marketplace add https://github.com/vatai/fn-agent-telemetry.git
claude plugin install fn-claude-telemetry@fn-agent-telemetry
```

Restart Claude Code, then check with `claude plugin details fn-claude-telemetry`
(9 hooks, 1 command). Uninstall with
`claude plugin uninstall fn-claude-telemetry@fn-agent-telemetry`.

### opencode

One line of config is the whole install: opencode resolves each `plugin` entry
as an npm specifier or a filesystem path, and the plugin registers its own
`/fn-eval`, so there is no second file to place.

Write it to `~/.config/opencode/opencode.json`. opencode loads and merges
`config.json`, `opencode.json` and `opencode.jsonc` from that directory, so a
separate file leaves an existing `opencode.jsonc` untouched.

From a checkout:

```json
{
  "plugin": [
    "/path/to/fn-agent-telemetry/plugins/opencode/plugin/agent-telemetry.js"
  ]
}
```

From a tarball, for a machine with no checkout — `npm pack` at the repo root
produces it, and it carries the Python package too:

```json
{ "plugin": ["file:/path/to/fn-agent-telemetry-0.1.0.tgz"] }
```

Or, once published to npm, in place of all of the above:

```sh
opencode plugin fn-agent-telemetry -g
```

Restart opencode; `/fn-eval` should appear in the command list. Per project
rather than per user, the same entry works in `./opencode.json`.

Point the entry at the plugin _inside_ its checkout or package — it locates the
shared Python package relative to its own file, so a copy taken out of the tree
will not work. Measured against opencode 1.18: an absolute path to the plugin
file, an absolute path to a package directory, and `file:<tarball>` all load;
`git+https://…​.git` and `github:owner/repo` are ignored with no error logged,
so installing straight from a git host is not an option.

## Rating a session: `/fn-eval`

Hooks record events from then on, with nothing to run. To archive a session, run
this once before you leave it:

```
/fn-eval
```

The agent proposes what the session should be judged on, then asks two
questions, one at a time — a figure of merit, then a value — and packs the
archive.

| Figure of merit | Rates                                           | You answer |
| --------------- | ----------------------------------------------- | ---------- |
| `satisfaction`  | how good the session was overall                | 1–5        |
| `correctness`   | did the work come out right                     | 1–5        |
| `code_quality`  | readability and fit with the surrounding code   | 1–5        |
| `autonomy`      | how little steering it needed                   | 1–5        |
| `trust`         | confidence in the result without re-checking it | 1–5        |
| `speedup`       | measured walltime vs the previous version       | a ratio, × |
| `time_saved`    | minutes saved vs doing it by hand               | minutes    |
| `iterations`    | corrections needed before it was right          | a count    |

The second question is worded from the answer to the first, which is why they
are asked separately: a rating offers 1–5, a measurement asks for the number you
observed. The scale — bounds, unit, and whether higher or lower is better — is
written onto the event, so ratings and measurements stay readable side by side
without this table. Values are validated against it, so an out-of-range rating
is an error rather than a stored number.

Claude Code asks the two questions as `AskUserQuestion` menus. opencode has no
such tool, so it asks them in prose and the answers arrive as free text; the
vocabulary and the scale are enforced in Python either way, and a value opencode
rejects makes the command re-ask.

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

The vocabulary is fixed so scores stay comparable across sessions and users;
anything it cannot express goes in `--comment`. Widen it in
`agent_telemetry/feedback.py` before collecting, not after.

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

| `event_type`     | Claude Code        | opencode              | Extra fields                                   |
| ---------------- | ------------------ | --------------------- | ---------------------------------------------- |
| `session_start`  | `SessionStart`     | `session.created`     | `source` (Claude Code)                         |
| `session_end`    | `SessionEnd`       | `session.deleted`     | `reason` (Claude Code)                         |
| `user_prompt`    | `UserPromptSubmit` | `chat.message`        | `prompt`                                       |
| `tool_pre`       | `PreToolUse`       | `tool.execute.before` | `tool_name`, `tool_input`                      |
| `tool_post`      | `PostToolUse`      | `tool.execute.after`  | `tool_name`, `tool_input`, `tool_response`     |
| `turn_end`       | `Stop`             | `session.idle`        | —                                              |
| `subagent_end`   | `SubagentStop`     | —                     | —                                              |
| `notification`   | `Notification`     | `session.error`       | `message`                                      |
| `compact`        | `PreCompact`       | `session.compacted`   | `trigger`, `custom_instructions` (Claude Code) |
| `permission_ask` | —                  | `permission.ask`      | `tool_name`, `message`, `status`               |
| `feedback`       | `SlashCommand`     | `SlashCommand`        | `subject`, `fom`, `scale`, `value`, `comment`  |

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

**There is no `AskUserQuestion` under opencode.** The two questions are asked in
prose instead of as a menu, so the answers arrive as free text. They are still
checked: the figure of merit is a fixed vocabulary and the value is parsed as a
number and validated against that figure's scale, all in Python. A rejected
value exits non-zero and the command re-asks.

## Reading the archives back

[`analysis/`](analysis) is the read side: `archives.py` turns each zip into one row —
session, activity counts, token usage, cost, rating — and `report.py` prints
those rows as a table, CSV or JSON. It imports nothing from the plugins and no
plugin install ships it; the archive is the interface between the two sides.

## Repo layout and status

[PLAN.md](PLAN.md) holds the goal, the specification, and the state of each
step. [AGENTS.md](AGENTS.md) is the brief for agents changing this repo. The
shared Python package lives at `plugins/claude-code/agent_telemetry/` and is
used by **both** plugins — the path is historical, not a scope.
