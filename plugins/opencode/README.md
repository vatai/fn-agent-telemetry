# opencode telemetry plugin

Archives an opencode session as one zip: the session's event log, its
transcript, and the user's own rating of how the session went. Same archives,
same event taxonomy and same `AGENT_TELEMETRY_DIR` as the Claude Code plugin in
`../claude-code`, so both agents' sessions land side by side in one directory.
Best-effort — it never interrupts a session.

## Usage

### 1. Install

One line of config is the whole install: opencode resolves each `plugin` entry
as an npm specifier or a filesystem path, and the plugin registers its own
`/fn-eval`, so there is no second file to place.

Write it to `~/.config/opencode/opencode.json`. opencode loads and merges
`config.json`, `opencode.json` and `opencode.jsonc` from that directory, so a
separate file leaves an existing `opencode.jsonc` untouched.

From a checkout:

```jsonc
{ "plugin": ["/path/to/clanker-telemetry/plugins/opencode/plugin/agent-telemetry.js"] }
```

From a tarball, for a machine with no checkout — `npm pack` at the repo root
produces it, and it carries the Python package too:

```jsonc
{ "plugin": ["file:/path/to/clanker-telemetry-0.1.0.tgz"] }
```

Or, once published to npm, in place of all of the above:

```sh
opencode plugin clanker-telemetry -g
```

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
```

Needs `python3` on `PATH`. Restart opencode; `/fn-eval` should appear in the
command list. Per project rather than per user, the same entry works in
`./opencode.json`.

Point the entry at the plugin *inside* its checkout or package — it locates the
shared Python package relative to its own file, so a copy taken out of the tree
will not work. Measured against opencode 1.18: an absolute path to the plugin
file, an absolute path to a package directory, and `file:<tarball>` all load;
`git+https://…​.git` and `github:owner/repo` are ignored with no error logged,
so installing straight from a git host is not an option.

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

Everything below the adapter is shared. These five things are not.

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

**The command ships inside the plugin.** A Claude Code plugin declares its
commands as files and the installer places them. Nothing places a file for an
opencode plugin installed from npm or a tarball, so the `config` hook registers
`/fn-eval` from `command/fn-eval.md` at load time — description read from the
frontmatter, body used as the template. An `fn-eval` the user has defined
themselves is left alone.

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
