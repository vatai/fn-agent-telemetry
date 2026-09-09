# Dev Notes

## Rating a session: `/fn-eval`

Hooks note that a session exists, with nothing to run. To produce its result,
run this once before you leave it:

```
/fn-eval          # $fn-eval under codex, where it is a skill and not a command
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
separately. Claude Code asks all three as `AskUserQuestion` menus. Neither
opencode nor codex has such a tool to reach for, so both ask in prose and the
answers arrive as free text; the numbers are checked in Python either way, and
an answer it rejects makes the command re-ask.

### Where the Q1 suggestions live

The suggestion list is written out in five places, because a markdown prompt
cannot import Python and each agent reads its own prompt. Add a figure to all of
them, or the agents offer different things:

| File                                              | What                                                                                                                   |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `plugins/claude-code/agent_telemetry/feedback.py` | `SUGGESTED_FOMS` — the canonical list: name, unit, what it suits. Only `--help` reads it; nothing validates against it. |
| `plugins/claude-code/commands/fn-eval.md`         | The step 2 table, offered as `AskUserQuestion` options.                                                                 |
| `plugins/opencode/command/fn-eval.md`             | The step 2 table, offered in prose.                                                                                    |
| `plugins/codex/skills/fn-eval/SKILL.md`           | The same table, offered in prose. A skill, not a command: codex installs no commands.                                  |
| `README.md`, `## FOM: Figure of merit`            | The user-facing prose version, and where the list came from.                                                            |

Nothing enforces agreement between them, since `--fom` accepts any name — a
list that has drifted produces valid but unevenly-prompted data, not an error.

**Skip `/fn-eval` and you get nothing.** Rating is the only thing that produces
a result. The document stays in `.pending/`, and under Claude Code the token
counts and cost are lost once it prunes `~/.claude/projects`, since that record
is where they live. The same goes for codex, whose token counts live in
`~/.codex/sessions`.

**Then close the session — Claude Code only.** `/fn-eval` writes the document
from inside the turn it runs in, and Claude Code records the session's cost only
as the session ends. So the `SessionEnd` hook writes a rated session's document
again. Rate and never exit, and the document has everything but the cost.
Neither of the others has that gap: opencode refreshes usage at the end of every
turn, and so does codex — its `Stop` hook writes a rated session out again,
which is also all there is to wait for, codex reporting no cost at any point.

Q3's 1–5 scale is what keeps scores comparable across sessions and users, so it
is fixed; Q1 is deliberately not. Anything the three numbers cannot express goes
in `--comment`.

## What is collected

Six things, and nothing else:

| | |
| - | - |
| **skills** | every skill the session had available, the text defining it, and how often it was used |
| **usage** | tokens per assistant message |
| **cost** | what the session cost, where the agent says — codex never does |
| **context** | the `AGENTS.md` and `CLAUDE.md` files in effect, whole |
| **tools** | which tools ran, and how many times each, and — under Claude Code alone — how often each skill was invoked |
| **rating** | your three answers |

No prompts, no assistant output, no tool inputs or results, no native hook
payloads, and no copy of the conversation. Tool activity is names and counts:
what a tool was given and what it returned are not read at all, save the one
field named under [tools](#tools) below. A hook's payload is read for the
session id, the working directory and where the agent keeps its own record, and
is then discarded — it is never stored. That matters more than it
sounds: a `Stop` payload carries the assistant's entire reply in
`last_assistant_message`, so keeping payloads wholesale is how conversation gets
collected by accident.

## Options

All three plugins need `python3` on `PATH`, and all three read the same one
setting:

```sh
export AGENT_TELEMETRY_DIR=~/somewhere-else          # optional; defaults to ~/agent-telemetry
```

One plugin per agent, one document format for all of them. Everything below the
adapter is shared — the same Python package, the same document, the same
`AGENT_TELEMETRY_DIR` — so every agent's sessions land side by side in one
directory, and `session.agent` says which one produced it.

## Uploading

Each run of `/fn-eval`, under any of the agents, leaves one file to send, in
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
are snapshotted at `SessionStart`, the rating arrives from `/fn-eval`, and
usage, cost and tool activity are read at the end. So a partial document accumulates in `.pending/`
in the same shape and is written out to the result name once rated. Nothing is
appended to — there is no event stream — so each change rewrites the document
whole, staged and renamed into place, and an interrupted write can never replace
a good document with half of one.

Written at least twice in the ordinary case: once by `/fn-eval`, and once after
it. For Claude Code that second pass is the `SessionEnd` hook, and it is what
picks up the cost. For opencode it is the end of every subsequent turn, and for
codex the same, through its `Stop` hook; each adapter's `FINALIZE_AT` names the
events it wants. Either way, a session that was never rated is not written out
at any point.

## Document format

One JSON object per session. No local path reaches it: `cwd` is the project
directory's name alone, paths under the session's directory are written
`$PROJECTS/<name>/...` so two checkouts of one project read alike, and anything
else under the home directory is written `$HOME/...` -- in the texts too, not
just the path fields. The pending document holds the real paths; `session.py`
rewrites them on the way out (`scrub.py`), since the lookups need them until
then.

`host.email` is resolved at the same point, by `identity.py`, descending until
something answers: the account Claude Code is signed in as, read from its own
`~/.claude.json`; else git's `user.email` as it reads in the project, so a
per-repo identity wins; else git's `user.name`, when a name is configured but no
address; else `user@hostname`. Only Claude Code has an account to read — codex
keeps its own in the file that holds its credentials, which is not a file this
reads — so the other two always start at the git rung. That last rung is the one place a
hostname is still recorded, there being nothing else left to tell two users
apart.

```json
{
  "schema_version": 4,
  "session": {
    "session_id": "610153d8-…",
    "agent": "claude-code",
    "cwd": "clanker-telemetry",
    "started": "2026-09-07T09:20:22.801751+00:00",
    "ended": "2026-09-07T09:31:04.113402+00:00",
    "host": { "os": "Linux 7.1.9-arch1-2 #1 SMP … x86_64", "user": "vatai",
              "email": "emil.vatai@riken.jp" }
  },
  "skills": [{ "name": "code-review", "source": "listing", "text": "Review the current diff…",
               "uses": 0 }],
  "tools": [{ "name": "Bash", "calls": 198 }, { "name": "Edit", "calls": 32 }],
  "usage": [{ "message_id": "msg_01…", "model": "claude-opus-5", "input": 2,
              "output": 452, "reasoning": 276, "cache_read": 129339, "cache_write": 974 }],
  "cost_usd": 4.13,
  "context": [{ "path": "$PROJECTS/clanker-telemetry/AGENTS.md",
                "names": ["…/AGENTS.md", "…/CLAUDE.md"], "text": "# fn-agent-telemetry…" }],
  "feedback": { "subject": "…", "fom": "hours_saved", "scale": {}, "value": 6,
                "satisfaction": 5, "satisfaction_scale": {}, "comment": null,
                "recorded": "2026-09-07T09:30:11.250566+00:00" }
}
```

`cost_usd` is absent or `null` when it could not be determined, which is not a
zero — and always `null` under codex, which reports no cost anywhere. A codex
document also differs in two smaller ways within the same schema: a usage row's
`message_id` is `null`, codex attributing usage to a request rather than a
message, and a skill carries no `uses` key at all, since nothing counts skill
invocations there. `feedback` is `null` in a pending document and always present in a result,
rating being what produces one. A pending document also carries `_record_path`,
which is bookkeeping — where the agent keeps its own record — and is dropped
before anything is written out, so no result names a local file.

### skills

`source` is the file the text came from, `listing` when there was no file and
the text is the one-line description instead, or `invocation` for a skill that
was used without appearing in any listing. Expect mostly
`listing`: of nineteen skills available in a measured session, **one** had a file
on disk, and it was a plugin's `commands/fn-eval.md` rather than a `SKILL.md`.
The other eighteen are built into the CLI and have no file to read.

The available set is not on disk either. Claude Code injects it into the
conversation as `skill_listing` records — the first carrying the full list, later
ones carrying additions when a plugin is installed mid-session — so the names are
folded across all of them. Verified on three sessions: nineteen each, and the
fold catches the one where a plugin arrived mid-way (18 + 1). opencode publishes
no such listing, so its `skills` is empty.

Codex publishes one too, in the `host_skills` body of a `world_state` record:
the same listing it showed the model, naming each skill's `SKILL.md` through a
table of short roots (`` `r0` = `~/.codex/skills/.system` ``). So codex is the
one agent whose skills mostly *do* have text on disk — six of six in a measured
session, against one of nineteen under Claude Code. Two caveats come with it.
Each body is the whole list rather than additions, so a later one wins per name
and the union is still what was available. And the listing is what the session
was *told* it had: codex shortens descriptions to fit a budget, and drops skills
from a large enough set. A codex session old enough to predate the record
carries no listing, and then `skills` is empty.

### tools

Names and counts. `tools` is every tool the session called, most-called first,
and `uses` on a skill is how many times that skill was invoked — the question
"which skills were actually used" that the available list alone cannot answer.

That count is the one place an input is read: a `Skill` call carries the name of
the skill in its `input`, so `tools.py` takes that field and discards the rest.
No other tool's input is looked at, deliberately — a `SlashCommand` carries the
command line the user typed, and that is conversation. It exists under Claude
Code only. Codex has no `Skill` tool to read — a skill there is invoked by name
in a prompt, or read off disk — and what a codex call does carry is the shell
command it ran, so no codex input is touched and no codex skill gets a `uses`.
A `0` would have claimed the skill went unused rather than uncounted, which is
why the key is absent instead.

A call is counted once per `tool_use` id under Claude Code, once per `callID`
under opencode and once per `call_id` under codex — over its `function_call` and
`custom_tool_call` items both — so a record that repeats a call cannot inflate
the count. Verified on a 2.9 MB Claude Code record: 259 calls over four tools,
identical deduped and not. A subagent's tools are missing everywhere — they are
written to a record of its own, which nothing opens. A skill invoked but absent
from the listing is kept with `invocation` as its `source` and no text, rather
than dropped.

### context

`AGENTS.md` and `CLAUDE.md` are collected whole, deliberately: they are what the
agent was told to do. Taken from the working directory, the directories above it,
and the user-level directories the agent's own adapter names — `~/.claude` under
Claude Code, `$CODEX_HOME` (`~/.codex`) under codex, and under opencode both
`~/.config/opencode` and `~/.claude` (see below). The two names are frequently one file — this repo keeps
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

Codex differs in the other direction: it writes a `token_count` event carrying
the whole session's counts **so far**, so a row is what they *grew by* since the
event before it. Summing the `last_token_usage` each event also carries would
over-count, for the same reason a per-record sum does under Claude Code: an
aborted turn re-reports the previous snapshot. Verified across all 22 rollouts on
one machine — every session's summed rows equal the count codex itself ended on,
and the session that re-reported a snapshot comes out at 28 rows rather than 29.
Its `input_tokens` includes the cached tokens, unlike Claude Code's, so both
cached kinds are taken out of `input`: a reader adds `input`, `cache_read` and
`cache_write` and gets the total codex reports. Cost is the part codex simply
does not have — its `rate_limits` say what a plan has left, not what a session
spent — so a codex `cost_usd` is always `null`.

## How the plugins differ

Everything below the adapter is shared. These are not.

**Hooks are a module, not a subprocess.** Claude Code and codex both declare
their hooks in a `hooks.json` and run an executable per event — codex's payload
carries the same `session_id`, `cwd`, `hook_event_name` and `transcript_path`,
so its adapter is nearly Claude Code's. opencode loads
`plugins/opencode/plugin/agent-telemetry.js` into its own process and calls
exported functions, so the plugin is what spawns the shared Python — passing the
same JSON on stdin, so the two capture paths converge immediately. It hooks only
the three lifecycle events; prompts, tool calls and tool results are not hooked
at all, so nothing is spawned on the hot path of a turn.

**opencode's usage arrives over the SDK.** It keeps its messages in a database
rather than a record on disk, so the plugin reads them back at the end of every
turn and hands them to `agent_telemetry.messages`, which takes the token counts,
the cost and the name of each `tool` part, and stores none of the message
content. Its skills carry no `uses`, since it publishes no listing to attach one
to; a skill it ran shows up as whatever tool ran it. That pass also rewrites the
document of a session already rated, because `/fn-eval` writes it in the middle
of the turn it runs in.

**Codex writes usage as it goes, and never writes a cost.** So a rated codex
session is written out at the end of every turn rather than only at
`SessionEnd`, which is what `FINALIZE_AT` on each adapter says. That also keeps
finalizing off a hook codex gives one second by default and three at most:
measured at ~90 ms against the largest rollout on this machine, but the
`SessionEnd` entry still asks for `timeout: 3` rather than relying on the
default.

**Codex's record has to be found, not trusted.** Its docs call
`transcript_path` explicitly not a stable interface, and their own example names
a rollout inside the project rather than under the codex home. So the adapter
uses that path only when it is really a file, and otherwise finds the rollout by
the session id every one of their names ends with.

**Codex has hooks nobody has trusted yet.** It refuses to run a hook until the
user reviews it under `/hooks`, so a fresh install collects nothing at all until
they do — which is worth saying in the install instructions, because the failure
mode is silence.

**Codex takes a skill where the others take a command.** Its custom prompts are
deprecated in favour of skills, so `/fn-eval` ships as
`plugins/codex/skills/fn-eval/SKILL.md` and is invoked `$fn-eval`. Two
consequences: it is symlinked into `~/.codex/skills` rather than installed, so
the skill resolves the feedback executable through its own file's real path; and
`agents/openai.yaml` sets `allow_implicit_invocation: false`, since codex would
otherwise be free to rate a session the user never asked to have rated.

**The user's instructions live somewhere else under opencode.** Claude Code
loads them from `~/.claude`; codex from `$CODEX_HOME`, or `~/.codex`; opencode loads `AGENTS.md` from its own global
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

**There is no `AskUserQuestion` under opencode or codex.** The three questions
are asked in prose instead of as menus, so the answers arrive as free text. The numbers
are still checked in Python — Q2 as a number of 0 or more, Q3 as a whole number
from 1 to 5 — and a rejected one exits non-zero so the command re-asks. Q1 is
not checked, because any figure of merit is accepted by design.

## Reading the results back

[`analysis/`](analysis) is the read side: `archives.py` turns each result into one
row — session, skills, usage, cost, context, tool activity, rating — and
`report.py` prints those rows as a table, CSV or JSON. Its `tools` column is
calls over distinct tools; the per-tool and per-skill counts are in the CSV and
JSON exports. A document written before tool activity was collected leaves those
columns blank rather than zero, which would claim no tool ran — and so does an
agent that cannot answer: `skill_calls` and `skills_used` are blank for codex
and opencode, and `cost` is blank for codex. Its `fom` column is that session's own figure and
unit and does not compare across sessions; `sat` is the Q3 normalisation that
does. It imports nothing from the plugins and no plugin install ships it; the
file on disk is the interface between the two sides.

It also still reads the old `.zip` archives, which held an event log and a copy
of the whole transcript. Those exist on other machines and some were already
sent, so they are read for what a document also carries — usage, cost, rating —
and their skill and context columns come out blank, which is the point: an
archive with the entire conversation in it cannot answer either question.

## Tests

```sh
tests/run                      # everything: stdlib unittest, python3 and nothing else
tests/run test_hook_binary     # one module
```

They run the plugins the way the agents run them — a wrapper as an executable
with one JSON payload on stdin, a shared entry point as `python3 -m` — inside a
temporary `HOME`, project directory and `AGENT_TELEMETRY_DIR`. The child's
environment is built rather than inherited, because `HOME` reaches four things
that would otherwise leak into a result: the instructions collected, the skill
lookup, the identity resolved, and the paths scrubbed on the way out.

| File | What |
| ---- | ---- |
| `tests/records.py` | The example inputs. Hand-built and small: each record stands for a rule above, not for a real session. `SENTINEL` marks every field that carries conversation. |
| `tests/flows.py` | A whole rated session per agent, in the order the agent produces one. |
| `tests/harness.py` | The sandbox, and the runners: `run_hook`, `run_feedback`, `run_module`. |
| `tests/test_hook_binary.py` | What one hook event does, and the failure modes that must stay silent. |
| `tests/test_feedback_binary.py` | `/fn-eval`: a whole result asserted per agent, and the answers it rejects. |
| `tests/test_messages_module.py` | opencode's usage pass, the entry point with no record to read. |
| `tests/test_no_conversation.py` | The sentinel scan: nothing written may contain it. |
| `tests/test_capture.py` | The rules on their own, for inputs a session cannot be built around. |
| `tests/test_analysis_reads_a_result.py` | `analysis/` reading what the binaries just wrote — the only check that the two sides agree. |

The sentinel test is the one that stands for the specification rather than for a
function: every conversation-bearing field of every input holds the same string,
and no byte under the telemetry directory may contain it. Storing a hook payload
fails it, which is the accident it exists to catch.

Three things are deliberately not covered. The opencode plugin's own JavaScript
needs node and a live SDK, so what is tested is the two module invocations it
makes. Codex firing its own hooks needs an interactive `/hooks` trust step.
And installation has no installer to test.

## Repo layout and status

[PLAN.md](PLAN.md) holds the goal, the specification, and what is left to do.
[AGENTS.md](AGENTS.md) is the brief for agents changing this repo. The shared
Python package lives at `plugins/claude-code/agent_telemetry/` and is used by
**all three** plugins — the path is historical, not a scope.
