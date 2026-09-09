# Goal

Collect detailed local usage information from Claude Code, codex and opencode CLI
sessions, through each agent's native integrations: what the session was configured
with, what it consumed, and how the user rated it.

# Specification

- Observe local CLI sessions of all three agents, interactive and non-interactive.
- Install integrations in per-user agent configuration.
- Collect only six things: the skills available to the session and their defining text;
  per-message token usage; the session cost, from the agents that report one; the
  contents of the `AGENTS.md` and `CLAUDE.md` instruction files in effect; which tools
  ran and how many times each; and the user's rating.
- Collect no conversation — no prompts, assistant output, tool inputs or outputs, or
  native hook payloads — and keep no copy of the session transcript. Tool activity is
  names and counts, plus the skill named by a `Skill` call where the agent names one,
  and nothing else.
- Record the user's own rating: a figure of merit of their choosing, and one fixed 1-5
  normalisation of it that compares across sessions and users.
- Retain results indefinitely under `AGENT_TELEMETRY_DIR`, as one JSON file per *rated*
  session. Not an archive, and not a directory.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

How each piece works is in `dev-notes.md`; this is what is left to do.

**Built.** Each plugin collects the six things and nothing else, into one JSON
document per rated session. A hook reads a payload for the session id, the
working directory and the record path, then discards it — Claude Code now
declares three hooks instead of nine, and opencode hooks no prompt, tool call or
tool result at all, so neither spawns anything on the hot path of a turn. Usage
and cost are read from each agent's own record and never copied; skills are
folded from the session's own listing and their defining text found on disk where
it exists; `AGENTS.md` and `CLAUDE.md` are snapshotted whole at `SessionStart`.
`/fn-eval` is still the only thing that produces output, and `SessionEnd` writes
a rated session again so it carries the cost. `analysis/` reads the documents and
still reads the old `.zip` archives.

Verified against a real session record, now 2.9 MB: 318 usage rows and `$5.51`,
both identical to what the old reader produced from the same session; 20 skills,
one with a file on disk; the `AGENTS.md`/`CLAUDE.md` symlink stored once under both
names; an unrated session produces nothing; unparseable and empty stdin are
dropped exiting 0; and a `PreToolUse` payload's command string reaches no file.

The user-level instruction directory is now per-agent, closing a gap where an
opencode user's global `AGENTS.md` (in `$XDG_CONFIG_HOME/opencode`, not
`~/.claude`) was never collected. Verified with both agents against the same
project: opencode collects the opencode global file, `~/.claude/CLAUDE.md` — which
it also loads — and the project file; Claude Code collects the latter two only.

Tool activity is the sixth thing, added after the first five: `tools.py` counts
calls per tool name from the record already read for usage, once per `tool_use`
id under Claude Code and once per `callID` under opencode, and attaches a `uses`
count to each skill so the skills a session *used* are distinguishable from the
ones it merely had. One input field is read and one only — a `Skill` call's
`skill`. Schema is now 3, stamped as the document is written out rather than as it was
started, so a session pending since the previous version ships as what it is; a
document without the field reads back blank rather than zero, since "not
collected" is not "ran no tools". Verified on the same
2.9 MB record: 259 calls over four tools, identical whether deduped or not, with
usage, cost and skills unchanged; on a second session, 107 calls over six tools
with the one `Skill` call attributed to `fn-claude-telemetry:fn-eval`; and
`analysis/report.py` renders v3, v2 and `.zip` rows side by side, the older two
blank in the tool columns. Verified through the real `/fn-eval` path too — the
feedback binary, not `finalize()` directly — so the result carries tool activity
at rating time and not only after `SessionEnd`; and a pending document faked
back to schema 2 with no `tools` key ships as 3 with the field filled.

No local path or machine name reaches a result. The document is scrubbed as it is
written out (`scrub.py`, called from `session.py`): `session.cwd` is the project
directory's name alone, paths under it become `$PROJECTS/<name>/...` so two
checkouts of one project read alike, and anything else under the home directory
becomes `$HOME/...` — in the collected texts too, not only the path fields, since
an `AGENTS.md` cites paths of its own. The pending document keeps the real paths,
which `resolve()` matches on and the skill and instruction lookups walk. `host`
now reports `os` — `uname -a` minus the node name — in place of `hostname`, and
`analysis/` has that column in its place, blank for results already written. It
also carries `email`, resolved at write-out by `identity.py`: Claude Code's
signed-in account from its own config, else the git `user.email` as it reads in
the project, else the git `user.name`, else `user@hostname` — the one place a
hostname is still worth having. Verified down all four rungs. A `context` entry reports the file as it was
loaded — `os.path.abspath`, not `realpath` — so a `CLAUDE.md` symlinked out of
the tree no longer reports where it points; the realpath stays the dedup key, so
an `AGENTS.md`/`CLAUDE.md` pair is still one entry under both names.
Verified against a real result: no home path survives anywhere in it. Schema is
4 and the plugins are 0.3.0: `host.hostname` is gone, `host.email` is new, and
every path in a document reads differently, so a reader can tell the two shapes
apart by the number rather than by sniffing a field.

**Codex is the third agent,** collected through its own hooks. Its payload
carries the same four lifecycle fields as Claude Code's, so the adapter is
nearly the same one; below it, everything is shared as before. What codex needed
of its own is this. Its `token_count` events carry the
session's counts cumulatively, so a usage row is what they grew by — which also
drops the snapshot an aborted turn repeats — and its `input_tokens` includes the
cached tokens, so both cached kinds come out of `input`. It reports no cost
anywhere, so `cost_usd` stays `null` and the read side leaves the column blank
rather than showing a zero. And it names no skill in a tool call, so its skills
carry no `uses` at all, absent being the honest answer where `0` would claim the
skills went unused; `analysis/` now blanks `skill_calls` for any document that
counts none, which changes opencode rows the same way. Skills come from the
`host_skills` body of a `world_state` record, whose file references make codex
the one agent whose skills mostly do have their defining text on disk.
`FINALIZE_AT` on each adapter replaced the old boolean: codex writes a rated
session out at the end of every turn as well as at `SessionEnd`, both because
its usage accumulates as the session runs and because `SessionEnd` is a hook
codex allows one second by default and three at most.

Schema stays 4: a codex document is the same shape, and `session.agent` is how a
reader tells it apart — a `null` cost and a skill with no `uses` are the
document saying what codex cannot report, not a new format. The plugins are
0.4.0. Codex is installed by clone and hook config rather than as a codex
plugin, because a marketplace install copies the plugin directory alone and the
shared Python lives outside it — the same constraint opencode already has — and
`/fn-eval` ships as a skill, invoked `$fn-eval`, codex having deprecated the
custom prompts that would have been a slash command.

Verified against every codex rollout on this machine (22 of them): each
session's summed usage rows equal the count codex itself ended on, the session
that repeated a snapshot coming out at 28 rows rather than 29; tool calls are
counted once per `call_id` over both call shapes; six skills read their text
off disk, and a rollout old enough to carry no listing yields none. Verified
through the wrappers rather than the Python: a `SessionStart` payload naming a
rollout that does not exist still finds the record by session id, and so does
one naming a rollout that exists but belongs to another session — a decoy at the
`<project>/.codex/rollout.jsonl` path codex's own documentation shows, which
would otherwise have been read as this session's usage. `/fn-eval`'s own binary
writes the result, a `Stop` payload rewrites it, and no home path, decoy path or
cost survives in it — while the Claude Code path re-run on a real record still
produces its 150 usage rows, its tool counts and its `uses` per skill.
Finalizing measured ~90 ms against the largest rollout here. What is *not*
verified: codex firing the hooks itself, which needs an interactive
`/hooks` trust step, so every payload above was fabricated to the documented
shape rather than received.

One caveat stands: the corpus is too small, and too mixed in feedback vintage,
to quote an aggregate from.

**There is a test suite,** `tests/`, run with `tests/run`: 79 tests, stdlib
`unittest`, no dependency beyond `python3`. It runs the plugins the way their
agents run them — each wrapper as an executable with one JSON payload on stdin,
each shared entry point as `python3 -m` — inside a temporary `HOME`, project
directory and `AGENT_TELEMETRY_DIR`, so a result cannot depend on the machine
that ran the tests. The example inputs are in `tests/records.py`, small enough
to read and each one standing for a rule rather than for a real session: a
message written as two content-block records, a `cost-state` pair with the
larger written first, a repeated `tool_use` id, a `Skill` call, a listing that a
later one adds to, codex's cumulative snapshots including the repeat an aborted
turn writes, and a decoy rollout at the path codex's own documentation shows.
`tests/flows.py` holds the whole sequence each agent runs to produce a rated
session, since two files need it.

What that buys: every field of a result asserted against a known input, for all
three agents; the failure modes required to stay silent (unparseable stdin, an
unknown agent, a telemetry directory that cannot be created) each exiting 0 with
nothing written; the answers `/fn-eval` rejects, exiting 2 so the command
re-asks; and one test that stands for the specification itself — every
conversation-bearing field of every input carries the same sentinel string, and
nothing under the telemetry directory may contain it. Verified by mutation:
dropping the tool-call dedup fails 6 tests, dropping the path scrub fails 3, and
storing a hook payload fails the sentinel scan. The read side runs too —
`analysis/archives.py` reads results the binaries just wrote — which is the only
check that the two sides agree on the document they share.

Not covered, and deliberately: the opencode plugin's own JavaScript, which needs
node and a live opencode SDK, so what is tested is the two module invocations it
makes; codex firing its hooks itself, which still needs an interactive `/hooks`
trust step; and installation, there being no installer to test yet.

1. **Decide what to do about `subject`.** It is the one piece of prose still
   collected, and the user never approves it: `fn-eval.md` step 1 is "Work out
   the subject yourself — do not ask", so the agent writes a description of the
   task and it is stored as given. In a real session it read "looking up the
   current weather and 3-day forecast for Edogawa City, Tokyo" — topic and
   location — from a document that otherwise held no trace of the conversation.
   Either drop the field, or state the derived subject in Q1's question text so
   the user sees and can correct it. The second is recommended: a row with no
   description of what the session was for is hard to interpret, and it adds no
   question and changes no answer. Left open because it touches `/fn-eval`, whose
   three questions are otherwise not to be moved.

2. **Install and status commands,** per-user: validate CLI support, merge
   telemetry-only hook configuration, and validate the output path. Showing and
   deleting what was already collected belongs here — the old `.zip` archives
   hold whole conversations, and so do the `.pending/*.jsonl` event logs of every
   session that was never rated, which nothing has ever pruned.

3. **The tests the suite cannot reach yet.** Idempotent installation, which
   waits on step 2 having an installer; and the opencode plugin's own
   JavaScript, which would need node and a live SDK to drive its three hooks
   rather than the two module invocations they make.
