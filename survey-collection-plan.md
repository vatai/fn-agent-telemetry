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
3. Add an opencode plugin under `plugins/opencode/`: a JS/TS module exporting a `Plugin` function (`@opencode-ai/plugin`, locally 1.17.9 against an opencode binary at 1.18.25 — pin it and check the hook surface against the installed binary) that returns hooks. Subscribe to the catch-all `event` hook for lifecycle (`session.created`, `session.idle`, `session.error`, `session.compacted`, `session.deleted`, `message.updated`, `message.part.updated`, `permission.asked`, `file.edited`, `command.executed`) plus the direct `chat.message`, `tool.execute.before`, and `tool.execute.after` hooks.
4. Write opencode events in-process from the plugin instead of spawning `agent-telemetry-hook` per event. Rationale: opencode has no stdin-per-event subprocess contract like Claude Code's `hooks.json`; a plugin is a module loaded into one long-lived Bun process. The opencode side shares the *schema* — `SCHEMA_VERSION`, `event_id`, `timestamp`, `agent`, `host`, `event_type`, `native_event`, `session_id`, `cwd`, `raw`, and the same `AGENT_TELEMETRY_LOG` append-only JSONL target — not the code. Open question: `message.part.updated` is expected to fire per streaming delta — measure the rate before finalizing, and coalesce or sample if needed.
5. Map opencode events onto the shared taxonomy and resolve the asymmetries: no direct `session_end` (candidates `session.idle`, `session.deleted`, the `dispose` hook), and opencode-only signals (`session.error`, `permission.asked`/`permission.replied`, `file.edited`, `command.executed`) that need either new `event_type` values shared across agents or an explicit drop.
6. Capture assistant output from opencode, via assistant message parts (`message.part.updated`) and `experimental.text.complete`.
7. Add per-user installation and status commands for all three agents (Codex, Claude Code, opencode) that validate CLI support, merge telemetry-only configuration, and validate the log path. opencode installs either as a file in `~/.config/opencode/plugins/` (auto-loaded at startup) or as an npm package name in the `plugin` array of `~/.config/opencode/opencode.jsonc`; the Claude Code marketplace manifest is not involved.
8. Test event normalization, transcript retention, non-blocking failures, and idempotent installation for all three agents.
