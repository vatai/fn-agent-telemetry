# Dev Notes

## Rating a session: `/fn-eval`

Hooks note that a session exists, with nothing to run. To produce its result,
run this once before you leave it:

```
/fn-eval
```

The agent proposes what the session should be judged on, then asks three
questions, one at a time, and writes the document.

| Question | Asks for                                    | You answer             |
| -------- | ------------------------------------------- | ---------------------- |
| Q1       | the figure of merit — what was measured     | a name, or your own    |
| Q2       | its value                                   | a number, in Q1's unit |
| Q3       | the session overall, that figure normalised | 1–5                    |

Q1 is free text. A useful figure of merit is domain-specific — GFLOP/s for a
kernel, samples/s for a training loop, × for an optimisation — so the eight the
command offers are suggestions, not a vocabulary, and a name typed instead of
picked is stored as given. The unit comes with the number rather than from a
lookup, and the figure's scale is written down as open-ended and without a
direction: `loss` falls where `accuracy` rises, and nothing can tell which a
name nobody declared in advance is.

Which is why Q3 exists. Free text alone would leave N sessions with N
incomparable metrics, so Q3 asks for the same figure normalised onto one 1–5
scale on every session: a 100× speedup is a 5, no change a 3, a slowdown a 1.
Direction lives there too, and is asked for rather than inferred. Q2 is
therefore bounded only below, while Q3 is validated properly — it is the one
field that compares across sessions and users.

Each question is worded from the answer before it, which is why they are asked
separately. Claude Code asks all three as `AskUserQuestion` menus. opencode has
no such tool, so it asks them in prose and the answers arrive as free text; the
numbers are checked in Python either way, and an answer it rejects makes the
command re-ask.

### Where the Q1 suggestions live

The suggestion list is written out in four places, because a markdown prompt
cannot import Python and each agent reads its own prompt. Add a figure to all of
them, or the agents offer different things:

| File                                              | What                                                                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `plugins/claude-code/agent_telemetry/feedback.py` | `SUGGESTED_FOMS` — the canonical list: name, unit, what it suits. Only `--help` reads it; nothing validates against it. |
| `plugins/claude-code/commands/fn-eval.md`         | The step 2 table, offered as `AskUserQuestion` options.                                                                 |
| `plugins/opencode/command/fn-eval.md`             | The step 2 table, offered in prose.                                                                                    |
| `README.md`, `## FOM: Figure of merit`            | The user-facing prose version, and where the list came from.                                                            |

Nothing enforces agreement between them, since `--fom` accepts any name — a
list that has drifted produces valid but unevenly-prompted data, not an error.

**Skip `/fn-eval` and you get nothing.** Rating is the only thing that produces
a result. The document stays in `.pending/`, and under Claude Code the token
counts and cost are lost once it prunes `~/.claude/projects`, since that record
is where they live.

**Then close the session — Claude Code only.** `/fn-eval` writes the document
from inside the turn it runs in, and Claude Code records the session's cost only
as the session ends. So the `SessionEnd` hook writes a rated session's document
again. Rate and never exit, and the document has everything but the cost.
opencode has no equivalent gap: it refreshes usage at the end of every turn.

Q3's 1–5 scale is what keeps scores comparable across sessions and users, so it
is fixed; Q1 is deliberately not. Anything the three numbers cannot express goes
in `--comment`.

## What is collected

Five things, and nothing else:

| | |
| - | - |
| **skills** | every skill the session had available, and the text defining it |
| **usage** | tokens per assistant message |
| **cost** | what the session cost |
| **context** | the `AGENTS.md` and `CLAUDE.md` files in effect, whole |
| **rating** | your three answers |

No prompts, no assistant output, no tool inputs or results, no tool activity, no
native hook payloads, and no copy of the conversation. A hook's payload is read
for the session id, the working directory and where the agent keeps its own
record, and is then discarded — it is never stored. That matters more than it
sounds: a `Stop` payload carries the assistant's entire reply in
`last_assistant_message`, so keeping payloads wholesale is how conversation gets
collected by accident.

## Options

Both plugins need `python3` on `PATH`, and both read the same one setting:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
```

One plugin per agent, one document format for both. Everything below the adapter
is shared — the same Python package, the same document, the same
`AGENT_TELEMETRY_DIR` — so both agents' sessions land side by side in one
directory, and `session.agent` says which one produced it.

## Uploading

Each run of `/fn-eval`, under either agent, leaves one file to send, in
`~/agent-telemetry` (or `$AGENT_TELEMETRY_DIR`):

```
20260904-164832-610153d8-b1f9-48dc-b2e6-43b8febca643.json
└──────┬──────┘ └────────────────┬───────────────────┘
  when the session               the agent's
  started, local time            session id
```

One per session, `<date>-<time>-<session_id>.json` — `YYYYMMDD-HHMMSS`, so a
listing is already in chronological order and the name is unique across users
and machines. Re-running `/fn-eval` overwrites the session's own file rather
than adding another, so the whole directory is always the complete set. It is
plain JSON: read it before you send it.

_TODO: where to send them._

## Output layout

```
~/agent-telemetry/
├── 20260904-164832-<session_id>.json   # <date>-<time>-<session_id>, the result
└── .pending/<session_id>.json          # the same document, still being assembled
```

`AGENT_TELEMETRY_DIR` is the only setting. Hooks no-op silently only when no
home directory can be resolved.

The document is named for when the session _started_, in local time — so
listings sort chronologically and re-running `/fn-eval` overwrites the result
instead of adding a near-identical one. Timestamps _inside_ are UTC.

A session's document is assembled over its life: the instructions it runs under
are snapshotted at `SessionStart`, the rating arrives from `/fn-eval`, and usage
and cost are read at the end. So a partial document accumulates in `.pending/`
in the same shape and is written out to the result name once rated. Nothing is
appended to — there is no event stream — so each change rewrites the document
whole, staged and renamed into place, and an interrupted write can never replace
a good document with half of one.

Written at least twice in the ordinary case: once by `/fn-eval`, and once after
it. For Claude Code that second pass is the `SessionEnd` hook, and it is what
picks up the cost. For opencode it is the end of every subsequent turn. Either
way, a session that was never rated is not written out at any point.

## Document format

One JSON object per session:

```json
{
  "schema_version": 2,
  "session": {
    "session_id": "610153d8-…",
    "agent": "claude-code",
    "cwd": "/home/vatai/code/clanker-telemetry",
    "started": "2026-09-07T09:20:22.801751+00:00",
    "ended": "2026-09-07T09:31:04.113402+00:00",
    "host": { "hostname": "niku", "user": "vatai" }
  },
  "skills": [{ "name": "code-review", "source": "listing", "text": "Review the current diff…" }],
  "usage": [{ "message_id": "msg_01…", "model": "claude-opus-5", "input": 2,
              "output": 452, "reasoning": 276, "cache_read": 129339, "cache_write": 974 }],
  "cost_usd": 4.13,
  "context": [{ "path": "/home/vatai/code/clanker-telemetry/AGENTS.md",
                "names": ["…/AGENTS.md", "…/CLAUDE.md"], "text": "# fn-agent-telemetry…" }],
  "feedback": { "subject": "…", "fom": "hours_saved", "scale": {}, "value": 6,
                "satisfaction": 5, "satisfaction_scale": {}, "comment": null,
                "recorded": "2026-09-07T09:30:11.250566+00:00" }
}
```

`cost_usd` is absent or `null` when it could not be determined, which is not a
zero. `feedback` is `null` in a pending document and always present in a result,
rating being what produces one. A pending document also carries `_record_path`,
which is bookkeeping — where the agent keeps its own record — and is dropped
before anything is written out, so no result names a local file.

### skills

`source` is the file the text came from, or the string `listing` when there was
no file and the text is the one-line description instead. Expect mostly
`listing`: of nineteen skills available in a measured session, **one** had a file
on disk, and it was a plugin's `commands/fn-eval.md` rather than a `SKILL.md`.
The other eighteen are built into the CLI and have no file to read.

The available set is not on disk either. Claude Code injects it into the
conversation as `skill_listing` records — the first carrying the full list, later
ones carrying additions when a plugin is installed mid-session — so the names are
folded across all of them. Verified on three sessions: nineteen each, and the
fold catches the one where a plugin arrived mid-way (18 + 1). opencode publishes
no such listing, so its `skills` is empty.

### context

`AGENTS.md` and `CLAUDE.md` are collected whole, deliberately: they are what the
agent was told to do. Taken from the working directory, the directories above it,
and the user-level directories the agent's own adapter names — `~/.claude` under
Claude Code, and under opencode both `~/.config/opencode` and `~/.claude` (see
below). The two names are frequently one file — this repo keeps
`AGENTS.md` and symlinks `CLAUDE.md` to it — so entries are keyed by the resolved
path and list every name that reached it, rather than storing the text twice.

### usage and cost

Neither reaches a hook payload under Claude Code. Audited across every hook type
but `PreCompact`: the only token-shaped fields anywhere are `SessionStart`'s
`context_tokens` and `estimated_cache_write_usd` on a resume, which are the size
of the context and an estimate of re-priming it — not what was consumed. So the
agent's own record is read for these, and nothing of it is kept.

Two rules are load-bearing. Claude Code writes one record per content block and
repeats the *whole* message's usage on each, so usage is summed **one per
`message.id`**; a per-record sum double-counts exactly the messages that thought
or called a tool. And cost comes from a `cost-state` record written as a session
ends, so take the **largest, never the last** — a session resumed after one was
written goes on to write another — with absence meaning unknown, never zero.

opencode differs: its plugin receives `tokens` and `cost` per message over the
SDK, so the numbers arrive already attributed and a `0` from a free model is a
real zero rather than a missing record.

## How the two plugins differ

Everything below the adapter is shared. These six things are not.

**Hooks are a module, not a subprocess.** Claude Code declares its hooks in
`hooks.json` and runs an executable per event. opencode loads
`plugins/opencode/plugin/agent-telemetry.js` into its own process and calls
exported functions, so the plugin is what spawns the shared Python — passing the
same JSON on stdin, so the two capture paths converge immediately. It hooks only
the three lifecycle events; prompts, tool calls and tool results are not hooked
at all, so nothing is spawned on the hot path of a turn.

**opencode's usage arrives over the SDK.** It keeps its messages in a database
rather than a record on disk, so the plugin reads them back at the end of every
turn and hands them to `agent_telemetry.messages`, which takes the token counts
and the cost and stores none of the message content. That pass also rewrites the
document of a session already rated, because `/fn-eval` writes it in the middle
of the turn it runs in.

**The user's instructions live somewhere else under opencode.** Claude Code
loads them from `~/.claude`; opencode loads `AGENTS.md` from its own global
config directory — `$XDG_CONFIG_HOME` or `~/.config`, then `opencode` — *and*
`~/.claude/CLAUDE.md` on top of it, unless `disableClaudeCodePrompt` is set. So
each adapter states its own `user_instruction_dirs()` and `context` collects
those; hardcoding `~/.claude` silently dropped an opencode user's global file.

**The opencode command ships inside the plugin.** A Claude Code plugin declares
its commands as files and the installer places them. Nothing places a file for
an opencode plugin installed from npm or a tarball, so the `config` hook
registers `/fn-eval` from `command/fn-eval.md` at load time — description read
from the frontmatter, body used as the template. An `fn-eval` the user has
defined themselves is left alone.

**There is no `${CLAUDE_PLUGIN_ROOT}` under opencode.** The plugin's `shell.env`
hook exports `AGENT_TELEMETRY_BIN` into the shell tool's environment, and
`/fn-eval` resolves the feedback executable through it.

**There is no `AskUserQuestion` under opencode.** The three questions are asked
in prose instead of as menus, so the answers arrive as free text. The numbers
are still checked in Python — Q2 as a number of 0 or more, Q3 as a whole number
from 1 to 5 — and a rejected one exits non-zero so the command re-asks. Q1 is
not checked, because any figure of merit is accepted by design.

## Reading the results back

[`analysis/`](analysis) is the read side: `archives.py` turns each result into one
row — session, skills, usage, cost, context, rating — and `report.py` prints those
rows as a table, CSV or JSON. Its `fom` column is that session's own figure and
unit and does not compare across sessions; `sat` is the Q3 normalisation that
does. It imports nothing from the plugins and no plugin install ships it; the
file on disk is the interface between the two sides.

It also still reads the old `.zip` archives, which held an event log and a copy
of the whole transcript. Those exist on other machines and some were already
sent, so they are read for what a document also carries — usage, cost, rating —
and their skill and context columns come out blank, which is the point: an
archive with the entire conversation in it cannot answer either question.

## Repo layout and status

[PLAN.md](PLAN.md) holds the goal, the specification, and what is left to do.
[AGENTS.md](AGENTS.md) is the brief for agents changing this repo. The shared
Python package lives at `plugins/claude-code/agent_telemetry/` and is used by
**both** plugins — the path is historical, not a scope.
