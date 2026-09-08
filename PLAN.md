# Goal

Collect detailed local usage information from Claude Code and opencode CLI sessions,
through each agent's native integrations: what the session was configured with, what it
consumed, and how the user rated it.

# Specification

- Observe local CLI sessions of both agents, interactive and non-interactive.
- Install integrations in per-user agent configuration.
- Collect only six things: the skills available to the session and their defining text;
  per-message token usage; the session cost; the contents of the `AGENTS.md` and
  `CLAUDE.md` instruction files in effect; which tools ran and how many times each; and
  the user's rating.
- Collect no conversation — no prompts, assistant output, tool inputs or outputs, or
  native hook payloads — and keep no copy of the session transcript. Tool activity is
  names and counts, plus the skill named by a `Skill` call, and nothing else.
- Record the user's own rating: a figure of merit of their choosing, and one fixed 1-5
  normalisation of it that compares across sessions and users.
- Retain results indefinitely under `AGENT_TELEMETRY_DIR`, as one JSON file per *rated*
  session. Not an archive, and not a directory.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

How each piece works is in `dev-notes.md`; this is what is left to do.

**Built.** Both plugins collect the six things and nothing else, into one JSON
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
`analysis/` has that column in its place, blank for results already written.
Verified against a real result: no home path survives anywhere in it.

One caveat stands: the corpus is too small, and too mixed in feedback vintage,
to quote an aggregate from.

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

3. **Tests** for skill discovery and the listing fold, usage extraction against a
   known record, context collection through a symlink, non-blocking failures, and
   idempotent installation.
