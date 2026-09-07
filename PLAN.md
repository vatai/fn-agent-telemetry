# Goal

Collect detailed local usage information from Claude Code and opencode CLI sessions,
through each agent's native integrations: what the session was configured with, what it
consumed, and how the user rated it.

# Specification

- Observe local CLI sessions of both agents, interactive and non-interactive.
- Install integrations in per-user agent configuration.
- Collect only five things: the skills available to the session and their defining text;
  per-message token usage; the session cost; the contents of the `AGENTS.md` and
  `CLAUDE.md` instruction files in effect; and the user's rating.
- Collect no conversation — no prompts, assistant output, tool inputs or outputs, tool
  activity, or native hook payloads — and keep no copy of the session transcript.
- Record the user's own rating: a figure of merit of their choosing, and one fixed 1-5
  normalisation of it that compares across sessions and users.
- Retain results indefinitely under `AGENT_TELEMETRY_DIR`, as one JSON file per *rated*
  session. Not an archive, and not a directory.
- Telemetry failures must never interrupt an agent session.
- IDE and cloud sessions are out of scope.

# Plan/Steps

How each piece works is in `dev-notes.md`; this is what is left to do.

**Built.** Both plugins collect the five things and nothing else, into one JSON
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

Verified against a real 1.2 MB session record: 97 usage rows and `$4.13`, both
identical to what the old reader produced from the same session; 19 skills, one
with a file on disk; the `AGENTS.md`/`CLAUDE.md` symlink stored once under both
names; an unrated session produces nothing; unparseable and empty stdin are
dropped exiting 0; and a `PreToolUse` payload's command string reaches no file.

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
