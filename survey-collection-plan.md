# Goal

Collect detailed local usage information from Claude Code through its native integrations.

# Specification

- Observe local Claude Code CLI sessions, including interactive and non-interactive terminal sessions.
- Install integrations in per-user agent configuration.
- Capture session lifecycle, prompts, tool activity, tool inputs and outputs, assistant output, errors, and raw native event payloads.
- Append plaintext JSONL telemetry indefinitely to the path configured by `AGENT_TELEMETRY_LOG`.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

1. **Done.** Implement an `agent-telemetry-hook` executable that receives native hook payloads on stdin and writes enriched JSONL events.
2. **Done.** Add a Claude Code adapter that normalizes native lifecycle and tool events while retaining raw payloads.
3. **Done.** Snapshot the session transcript. Assistant output, token usage and cost are all absent from the nine hook payloads but present in the transcript at `transcript_path`, so copy it to `<log dir>/agent-telemetry-transcripts/<session_id>.jsonl` on `Stop` and `SessionEnd`, plus a `/snapshot` command for manual runs. Note the Specification describes only the `AGENT_TELEMETRY_LOG` JSONL and is silent on transcript copies as a second artifact.
4. Decide what the hook log should still carry now that the transcript is captured. Prompts, tool inputs and tool responses are duplicated there, while permission prompts (`notification`), `tool_pre` for denied or cancelled calls, `session_end.reason` and the `host` block have no transcript equivalent.
5. Add per-user installation and status commands that validate CLI support, merge telemetry-only hook configuration, and validate the log path.
6. Test event normalization, transcript retention, non-blocking failures, and idempotent installation.
