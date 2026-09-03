# fn-claude-telemetry (Claude Code plugin)

Appends JSONL telemetry for every local Claude Code CLI session to the path in
`AGENT_TELEMETRY_LOG`. Telemetry is best-effort and never interrupts a session.

## Distribute & install

The plugin is served from the marketplace manifest at the repo root
(`.claude-plugin/marketplace.json`). To use it:

```sh
export AGENT_TELEMETRY_LOG=~/agent-telemetry.jsonl   # add to your shell profile
claude plugin marketplace add /path/to/clanker       # or a git URL / GitHub repo
claude plugin install fn-claude-telemetry@clanker-telemetry
```

Requires `python3` on `PATH`. Verify with `claude plugin details fn-claude-telemetry`
(9 hooks) and remove with `claude plugin uninstall fn-claude-telemetry@clanker-telemetry`.

If `AGENT_TELEMETRY_LOG` is unset, hooks run and no-op silently.

## Generated log file

`AGENT_TELEMETRY_LOG` is an append-only JSONL file: one JSON object per line,
one line per hook event, retained indefinitely. Each object has:

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

If stdin cannot be parsed as JSON it is preserved verbatim under
`raw._unparsed_stdin` and `event_type` is `unknown`.

### Example line

```json
{"schema_version":1,"event_id":"82e9…","timestamp":"2026-09-01T23:37:59.768468+00:00","agent":"claude-code","host":{"hostname":"niku","pid":99936,"user":"vatai"},"event_type":"user_prompt","native_event":"UserPromptSubmit","session_id":"live1","cwd":"/some/project","transcript_path":null,"prompt":"refactor foo","raw":{"session_id":"live1","cwd":"/some/project","hook_event_name":"UserPromptSubmit","prompt":"refactor foo"}}
```
