# opencode telemetry plugin

Archives an opencode session as one zip: the session's event log, its
transcript, and the user's own rating of how the session went. Same archives,
same event taxonomy and same `AGENT_TELEMETRY_DIR` as the Claude Code plugin in
`../claude-code`, so both agents' sessions land side by side in one directory.
Best-effort — it never interrupts a session.

## Usage

### 1. Install

opencode loads plugins and commands from its own config directory, so link this
directory's two files into it:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
mkdir -p ~/.config/opencode/plugin ~/.config/opencode/command
ln -s "$PWD/plugin/agent-telemetry.js" ~/.config/opencode/plugin/
ln -s "$PWD/command/fn-eval.md" ~/.config/opencode/command/
```

**Link, do not copy.** The plugin locates the shared Python package relative to
its own file, so it has to stay inside the checkout. Needs `python3` on `PATH`.
Restart opencode; `/fn-eval` should appear in the command list.

Per project instead of per user, use `.opencode/plugin/` and `.opencode/command/`.

### 2. Use

Hooks record events from then on, with nothing to run. To archive a session, run
this once before you leave it:

```
/fn-eval
```

opencode proposes what the session should be judged on, then asks two questions,
one at a time — a figure of merit, then a value — and packs the archive. The
figure-of-merit vocabulary, the scales, and the validation are the shared ones;
see `../claude-code/README.md` for the table and the reasoning.

**Skip `/fn-eval` and you get no archive.** Nothing else triggers one.

### 3. Upload

Identical to the Claude Code plugin: one `<date>-<time>-<session_id>.zip` per
rated session in `~/agent-telemetry` (or `$AGENT_TELEMETRY_DIR`). The `agent`
field on every event says which agent produced it.

## What differs from the Claude Code plugin

Everything below the adapter is shared. These four things are not.

**Hooks are a module, not a subprocess.** Claude Code declares nine hooks in
`hooks.json` and runs an executable per event. opencode loads
`plugin/agent-telemetry.js` into its own process and calls exported functions,
so this plugin is what spawns the shared Python — passing the same JSON on
stdin, so the two agents' capture paths converge immediately.

**There is no transcript file.** opencode keeps its messages in a database.
The plugin reads them back over the SDK at the end of every turn and dumps them
to `.pending/<session_id>.transcript.jsonl`, which is the path the adapter
reports as `transcript_path`. That dump also repacks a session that has already
been rated, because `/fn-eval` packs its archive in the middle of the turn it
runs in — without the repack, the archive would miss that last turn.

**There is no `${CLAUDE_PLUGIN_ROOT}`.** The plugin's `shell.env` hook exports
`AGENT_TELEMETRY_BIN` into the shell tool's environment, and `/fn-eval` resolves
the feedback executable through it.

**There is no `AskUserQuestion`.** The two questions are asked in prose instead
of as a menu, so the answers arrive as free text. They are still checked: the
figure of merit is a fixed vocabulary and the value is parsed as a number and
validated against that figure's scale, all in Python. A rejected value exits
non-zero and the command re-asks.

## Event log format

The shared format, documented in `../claude-code/README.md`. What is
opencode-specific:

| Field          | Value                                                             |
| -------------- | ----------------------------------------------------------------- |
| `agent`        | `opencode`                                                        |
| `native_event` | The opencode hook or bus event name, e.g. `tool.execute.before`   |
| `cwd`          | The plugin's `directory`; no opencode payload carries one         |
| `raw`          | The payload the plugin assembled, native fields intact            |

| `event_type`     | `native_event`         | Extra fields                               |
| ---------------- | ---------------------- | ------------------------------------------ |
| `session_start`  | `session.created`      | —                                          |
| `session_end`    | `session.deleted`      | —                                          |
| `user_prompt`    | `chat.message`         | `prompt`                                   |
| `tool_pre`       | `tool.execute.before`  | `tool_name`, `tool_input`                  |
| `tool_post`      | `tool.execute.after`   | `tool_name`, `tool_input`, `tool_response` |
| `turn_end`       | `session.idle`         | —                                          |
| `notification`   | `session.error`        | `message`                                  |
| `compact`        | `session.compacted`    | —                                          |
| `permission_ask` | `permission.ask`       | `tool_name`, `message`, `status`           |
| `feedback`       | `SlashCommand`         | `subject`, `fom`, `scale`, `value`, `comment` |

`permission_ask` has no Claude Code counterpart and is kept because how often a
session had to stop and ask is a signal nothing else carries. Claude Code's
`subagent_end` has no counterpart here; opencode subagents run as sessions of
their own, with a `parentID`.

## Transcript format

`transcript.jsonl` holds one opencode message per line, exactly as
`GET /session/{id}/message` returned it: `{"info": …, "parts": […]}`. `info`
carries the role, the model, and for assistant messages the `tokens` and `cost`
of that message; `parts` carries the text, reasoning and tool calls. The shape
is opencode's, not this plugin's, and changes between releases — the above was
observed on **v1.18**.
