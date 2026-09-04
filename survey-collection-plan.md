# Goal

Collect detailed local usage information from Claude Code through its native integrations.

# Specification

- Observe local Claude Code CLI sessions, including interactive and non-interactive terminal sessions.
- Install integrations in per-user agent configuration.
- Capture session lifecycle, prompts, tool activity, tool inputs and outputs, assistant output, errors, and raw native event payloads.
- Retain telemetry indefinitely under the directory configured by `AGENT_TELEMETRY_DIR`, one zip archive per session holding that session's JSONL event log and transcript.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

1. **Done.** Implement an `agent-telemetry-hook` executable that receives native hook payloads on stdin and writes enriched JSONL events.
2. **Done.** Add a Claude Code adapter that normalizes native lifecycle and tool events while retaining raw payloads.
3. **Done.** Snapshot the session transcript. Assistant output, token usage and cost are all absent from the nine hook payloads but present in the transcript at `transcript_path`, so pack it together with the event log into `<AGENT_TELEMETRY_DIR>/<date>-<time>-<session_id>.zip`, named for when the session started so listings sort chronologically and repacking replaces one archive rather than adding another. No hook triggers a snapshot; archiving happens only as the last step of `/feedback`.
4. **Done.** Collect user feedback, since telemetry measures what a session did but not whether it was any good. `/feedback` asks two questions — a figure of merit from a fixed vocabulary, and a 1–5 score where 5 is best — and appends the answer to the session's own event log as `event_type: "feedback"`, sharing its `session_id` with every other event so the two halves need no join. The vocabulary is fixed to keep scores comparable across sessions and users; free wording goes in `comment`. `/feedback` also packs the archive, making it the plugin's only command. Note the Specification above describes only events and transcripts, so it does not yet account for feedback.
5. Decide what the hook log should still carry now that the transcript is captured. Prompts, tool inputs and tool responses are duplicated there, while permission prompts (`notification`), `tool_pre` for denied or cancelled calls, `session_end.reason` and the `host` block have no transcript equivalent.
6. Add per-user installation and status commands that validate CLI support, merge telemetry-only hook configuration, and validate the log path.
7. Test event normalization, transcript retention, non-blocking failures, and idempotent installation.
