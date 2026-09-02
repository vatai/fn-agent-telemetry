# Goal

Collect detailed local usage information from Codex and Claude Code through their native integrations.

# Specification

- Observe local Codex and Claude Code CLI sessions, including interactive and non-interactive terminal sessions.
- Install integrations in per-user agent configuration.
- Capture session lifecycle, prompts, tool activity, tool inputs and outputs, assistant output, errors, and raw native event payloads.
- Append plaintext JSONL telemetry indefinitely to the path configured by `AGENT_TELEMETRY_LOG`.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

1. Implement a shared `agent-telemetry-hook` executable that receives native hook payloads on stdin and writes enriched JSONL events.
2. Add separate Codex and Claude Code adapters that normalize native lifecycle and tool events while retaining raw payloads.
3. Add per-user installation and status commands that validate CLI support, merge telemetry-only hook configuration, and validate the log path.
4. Test event normalization, transcript retention, non-blocking failures, and idempotent installation for both agents.
