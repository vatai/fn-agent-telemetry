# fn-claude-telemetry (Claude Code plugin)

Archives a Claude Code CLI session as one zip: the session's hook-event log, its
transcript, and the user's own rating of how the session went. Best-effort — it
never interrupts a session.

## Usage

### 1. Install

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
claude plugin marketplace add /path/to/clanker       # or a git URL / GitHub repo
claude plugin install fn-claude-telemetry@clanker-telemetry
```

Needs `python3` on `PATH`. Restart Claude Code, then check with
`claude plugin details fn-claude-telemetry` (9 hooks, 1 command). Uninstall with
`claude plugin uninstall fn-claude-telemetry@clanker-telemetry`.

### 2. Use

Hooks record events from then on, with nothing to run. To archive a session, run
this once before you leave it:

```
/fn-eval
```

Claude proposes what the session should be judged on, then asks two questions —
a figure of merit, and a score from 1 to 5 where 5 is best — and packs the
archive.

| Figure of merit  | Rates                                            |
| ---------------- | ------------------------------------------------ |
| `correctness`    | did the work come out right                      |
| `time_saved`     | faster than doing it by hand                     |
| `few_iterations` | how close to right on the first try              |
| `code_quality`   | readability and fit with the surrounding code    |
| `autonomy`       | how little steering it needed                    |
| `trust`          | confidence in the result without re-checking it  |

**Skip `/fn-eval` and you get no archive.** Nothing else triggers one — not a
hook, not session end. The events survive in `.pending/`, but the transcript,
and with it the token counts and cost, is gone once Claude Code prunes
`~/.claude/projects`.

The vocabulary is fixed so scores stay comparable across sessions and users;
anything it cannot express goes in `--comment`. Widen it in
`agent_telemetry/feedback.py` before collecting, not after.

### 3. Upload

*TODO.*

## Output layout

```
~/agent-telemetry/
├── 20260904-164832-<session_id>.zip    # <date>-<time>-<session_id>
│   ├── events.jsonl                   # hook events, plus the user's rating
│   └── transcript.jsonl               # copy of the session transcript
└── .pending/<session_id>.jsonl        # live event log, folded in at each snapshot
```

`AGENT_TELEMETRY_DIR` is the only setting. Hooks no-op silently only when no
home directory can be resolved.

One archive per session, named for when the session *started*, in local time —
so listings sort chronologically and re-running `/fn-eval` overwrites the
archive instead of adding a near-identical one. Timestamps *inside* are UTC.

A zip cannot be appended to and each hook is its own process, so events
accumulate in `.pending/` and the archive is rewritten whole each time. It is
staged and renamed into place, so an interrupted run never damages the previous
archive. A session with no transcript yet is archived with `events.jsonl` alone.

## Event log format

`events.jsonl` is append-only, one JSON object per line, retained indefinitely.
Every object has:

| Field             | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| `schema_version`  | Event schema version (currently `1`).                                   |
| `event_id`        | Unique UUID for this event.                                             |
| `timestamp`       | ISO-8601 UTC time the event was recorded.                               |
| `agent`           | Source agent — `claude-code`.                                           |
| `host`            | `{hostname, pid, user}` of the process that emitted the event.          |
| `event_type`      | Normalized type shared across agents (see below).                       |
| `native_event`    | Original Claude Code hook name (e.g. `PreToolUse`).                      |
| `session_id`      | Claude Code session id.                                                 |
| `cwd`             | Session working directory.                                              |
| `transcript_path` | Path to the session transcript, when provided.                          |
| `raw`             | The unmodified native hook payload, for lossless capture.               |

Plus, per `event_type`:

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

Every row but the last comes from a hook; `feedback` is written by `/fn-eval`.
It shares the session's `session_id` with every other event, so usage and rating
need no join. If stdin cannot be parsed as JSON it is kept verbatim under
`raw._unparsed_stdin` with `event_type` `unknown`.

A `turn_end` line:

```json
{"schema_version":1,"event_id":"a583fb72-…","timestamp":"2026-09-03T23:32:39.127497+00:00","agent":"claude-code","host":{"hostname":"niku","pid":8848,"user":"vatai"},"event_type":"turn_end","native_event":"Stop","session_id":"610153d8-…","cwd":"/home/vatai/code/clanker-telemetry","transcript_path":"/home/vatai/.claude/projects/-home-vatai-code-clanker-telemetry/610153d8-….jsonl","raw":{"session_id":"610153d8-…","transcript_path":"…","cwd":"…","hook_event_name":"Stop","stop_hook_active":false}}
```

## Transcript format

`transcript.jsonl` is a verbatim copy of Claude Code's own transcript, so its
shape is Claude Code's, not this plugin's. It is undocumented upstream and does
change between releases; the below was observed on **v2.x, September 2026** and
is a guide, not a contract.

One JSON object per line, discriminated by `type`. Conversation records
(`assistant`, `user`, `system`, `attachment`) share an envelope of `uuid`,
`parentUuid`, `sessionId`, `timestamp`, `cwd`, `gitBranch`, `version`,
`isSidechain` and `userType`; session-state records carry only `sessionId`.

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

Neither reaches a hook payload — the transcript is the only place they appear.

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
transcript both records sat at lines 249 and 251, so the last is not necessarily
final. Summing `message.usage` across `assistant` records is the reliable route
to a session total.
