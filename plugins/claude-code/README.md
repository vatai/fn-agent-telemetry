# fn-claude-telemetry (Claude Code plugin)

Archives every local Claude Code CLI session as a zip holding that session's
hook-event log and its transcript. Telemetry is best-effort and never interrupts
a session.

## Layout

Everything goes in one directory, `~/agent-telemetry` unless
`AGENT_TELEMETRY_DIR` says otherwise. It is the only setting.

```
~/agent-telemetry/
├── <session_id>.zip
│   ├── events.jsonl                   # one JSON object per hook event
│   └── transcript.jsonl               # copy of the session transcript
└── .pending/<session_id>.jsonl        # live event log, folded in at each snapshot
```

One archive per session. A zip cannot be appended to and each hook runs as its
own process, so events accumulate in `.pending/` and the archive is rewritten
whole at every snapshot. Since snapshots are manual, a session that is never
snapshotted has no archive at all and `.pending/` holds everything kept of it —
its transcript, and so its token counts and cost, are lost once Claude Code
prunes `~/.claude/projects`.

## Distribute & install

The plugin is served from the marketplace manifest at the repo root
(`.claude-plugin/marketplace.json`). To use it:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; add to your shell profile
claude plugin marketplace add /path/to/clanker       # or a git URL / GitHub repo
claude plugin install fn-claude-telemetry@clanker-telemetry
```

Requires `python3` on `PATH`. Verify with `claude plugin details fn-claude-telemetry`
(9 hooks) and remove with `claude plugin uninstall fn-claude-telemetry@clanker-telemetry`.

Hooks no-op silently only when no home directory can be resolved.

## Snapshots

Token usage, cost and assistant output never reach a hook payload; they live in
the session transcript. A snapshot repacks the session archive from the pending
event log and the current transcript. The zip is staged and renamed into place,
so an interrupted snapshot never damages the previous archive, and each one
fully replaces the last — both sources are append-only. A session with no
transcript yet is archived with `events.jsonl` alone.

Snapshots are manual only: run `/snapshot`, and nothing is archived if you never
do. The hooks record events but never trigger one, so ending a session without
`/snapshot` leaves that session's data in `.pending/` and no zip. A slash command
receives no session id, so it recovers the session from the transcript paths
already in the telemetry log: the paths recorded for the current directory, most
recently written first.

## Feedback

Telemetry says what a session did, never whether it was any good. `/feedback`
records the other half: Claude proposes what the session should be judged on,
then asks the user two questions — which figure of merit, and a score from 1 to
5 where 5 is best. The answer is appended to the same `events.jsonl` as every
hook event, so it shares the session's `session_id` and needs no join, and the
archive is repacked immediately so it does not sit unarchived in `.pending/`.

| Figure of merit  | Rates                                            |
| ---------------- | ------------------------------------------------ |
| `correctness`    | did the work come out right                      |
| `time_saved`     | faster than doing it by hand                     |
| `few_iterations` | how close to right on the first try              |
| `code_quality`   | readability and fit with the surrounding code    |
| `autonomy`       | how little steering it needed                    |
| `trust`          | confidence in the result without re-checking it  |

The vocabulary is fixed on purpose: a free-form figure of merit gives N sessions
N incomparable metrics. Every one above is scored on the same 1–5 scale in the
same direction, and the scale travels with the event so a score is readable
without this table. Anything the scale cannot express goes in `comment`.

Scores and vocabulary are validated before anything is written, so a bad score
is an error rather than a stored value. If no transcript can be resolved the
answer is still written — to `.pending/unknown-session.jsonl` — since losing a
reply a human just gave costs more than an unarchived event.

## Event log format

`events.jsonl` is append-only: one JSON object per line, one line per hook event
of that session, retained indefinitely. Each object has:

| Field             | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| `schema_version`  | Event schema version (currently `1`).                                   |
| `event_id`        | Unique UUID for this event.                                             |
| `timestamp`       | ISO-8601 UTC time the event was recorded.                               |
| `agent`           | Source agent — `claude-code`.                                           |
| `host`            | `{hostname, pid, user}` of the process that emitted the event.          |
| `event_type`      | Normalized type shared across agents (see table below).                 |
| `native_event`    | Original Claude Code hook name (e.g. `PreToolUse`).                      |
| `session_id`      | Claude Code session id.                                                 |
| `cwd`             | Session working directory.                                              |
| `transcript_path` | Path to the session transcript, when provided.                          |
| `raw`             | The unmodified native hook payload, for lossless capture.               |

Event-specific fields are added per `event_type`:

| `event_type`    | `native_event`     | Extra fields                              |
| --------------- | ------------------ | ----------------------------------------- |
| `session_start` | `SessionStart`     | `source`                                  |
| `session_end`   | `SessionEnd`       | `reason`                                  |
| `user_prompt`   | `UserPromptSubmit` | `prompt`                                  |
| `tool_pre`      | `PreToolUse`       | `tool_name`, `tool_input`                 |
| `tool_post`     | `PostToolUse`      | `tool_name`, `tool_input`, `tool_response`|
| `turn_end`      | `Stop`             | —                                         |
| `subagent_end`  | `SubagentStop`     | —                                         |
| `notification`  | `Notification`     | `message`                                 |
| `compact`       | `PreCompact`       | `trigger`, `custom_instructions`          |
| `feedback`      | `SlashCommand`     | `subject`, `fom`, `scale`, `value`, `comment` |

Every row but the last comes from a hook. `feedback` is written by `/feedback`
(see below), not by Claude Code.

If stdin cannot be parsed as JSON it is preserved verbatim under
`raw._unparsed_stdin` and `event_type` is `unknown`.

### Example line

A `turn_end`:

```json
{"schema_version":1,"event_id":"a583fb72-…","timestamp":"2026-09-03T23:32:39.127497+00:00","agent":"claude-code","host":{"hostname":"niku","pid":8848,"user":"vatai"},"event_type":"turn_end","native_event":"Stop","session_id":"610153d8-…","cwd":"/home/vatai/code/clanker-telemetry","transcript_path":"/home/vatai/.claude/projects/-home-vatai-code-clanker-telemetry/610153d8-….jsonl","raw":{"session_id":"610153d8-…","transcript_path":"…","cwd":"…","hook_event_name":"Stop","stop_hook_active":false}}
```

## Snapshot format

`transcript.jsonl` is a verbatim copy of Claude Code's own transcript, so its shape is Claude Code's, not this plugin's. It is undocumented
upstream and does change between releases; what follows was observed on
**v2.x, September 2026** and is a guide, not a contract.

One JSON object per line, discriminated by `type`. Conversation records
(`assistant`, `user`, `system`, `attachment`) share an envelope of `uuid`,
`parentUuid`, `sessionId`, `timestamp`, `cwd`, `gitBranch`, `version`,
`isSidechain` and `userType`; the session-state records carry only `sessionId`.

| `type`                  | Holds                                                                        |
| ----------------------- | ---------------------------------------------------------------------------- |
| `assistant`             | `message` with `model`, `usage`, `stop_reason`, and `requestId`               |
| `user`                  | `message`; tool results also carry `toolUseResult`                            |
| `attachment`            | Injected context — `total_tokens_reminder`, `edited_text_file`, `skill_listing` … |
| `system`                | `subtype`: `turn_duration`, `stop_hook_summary`, `away_summary`               |
| `cost-state`            | `totalCostUSD`, `modelUsage` per model, `totalDuration`, `totalLinesAdded`     |
| `file-history-snapshot` | `snapshot` of files touched, keyed by `messageId`                             |
| `queue-operation`, `mode`, `permission-mode`, `last-prompt`, `ai-title`, `atis-latch` | UI and session state |

`message.content` is a list of parts: `text`, `thinking`, `tool_use`,
`server_tool_use` on `assistant`; `text` and `tool_result` on `user`.

### Token usage and cost

Neither reaches a hook payload — the snapshot is the only place they appear.

Per assistant message, `message.usage`:

```json
{"input_tokens":2,"cache_creation_input_tokens":974,"cache_read_input_tokens":129339,
 "output_tokens":452,"output_tokens_details":{"thinking_tokens":276},
 "server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard"}
```

Cumulative, in `cost-state`:

```json
{"type":"cost-state","totalCostUSD":5.50866775,"totalAPIDuration":620673,
 "modelUsage":{"claude-opus-5":{"inputTokens":307022,"outputTokens":39713,
   "thinkingTokens":8802,"cacheReadInputTokens":3457724,
   "cacheCreationInputTokens":126957,"webSearchRequests":0,"costUSD":5.5077257500000005}}}
```

`cost-state` is written at checkpoints, not only at the end — in one 539-line
transcript both records sat at lines 249 and 251, so the last one is not
necessarily final. Summing `message.usage` across `assistant` records is the
reliable route to a session total.
