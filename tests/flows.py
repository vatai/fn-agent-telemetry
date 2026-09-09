"""A whole rated session per agent, in the order the agent produces one.

Each function here is the sequence a real session runs: the hooks its agent
fires, the record its agent keeps, and then `/fn-eval`. They return the feedback
run so a caller can assert on what it printed, and leave the paths they created
on the test case.

They live apart from the tests because two files need the same sequences: the
one that asserts what a result contains, and the one that asserts what it must
never contain.
"""

import json
import os

import records

ANSWERS = {
    "subject": "a rewrite of the kernel",
    "fom": "hours_saved",
    "unit": "h",
    "value": 6,
    "satisfaction": 5,
}


def rate_claude_session(case, **answers):
    """A Claude Code session: `SessionStart`, work, `/fn-eval`.

    The cost is already in the record here; in a real session it arrives only as
    the session ends, which is why `SessionEnd` writes a rated session again.
    """
    case.claude_account()
    write_instructions(case)
    case.skill_file = case.write_file(
        os.path.join(case.project, ".claude", "commands", "fn-eval.md"), records.SKILL_TEXT
    )
    case.record = case.write_record(
        os.path.join(case.home, ".claude", "projects", "widget", "session.jsonl"),
        records.claude_record(),
    )
    payload = records.claude_payload("SessionStart", case.project, case.record)
    case.run_hook("claude-code", payload)
    return case.run_feedback("claude-code", **(ANSWERS | answers))


def rate_codex_session(case, session_id=records.SESSION_ID, **answers):
    """A codex session, whose payload names a rollout that is not its own.

    `transcript_path` is documented as unstable and codex's own example points
    inside the project, so the decoy written there is what the payload names and
    the rollout under `$CODEX_HOME` is what must be read.
    """
    case.git_identity()
    skills_root = os.path.join(case.codex_home, "skills")
    case.skill_file = case.write_file(
        os.path.join(skills_root, "fn-eval", "SKILL.md"), records.SKILL_TEXT
    )
    case.record = case.write_record(
        os.path.join(
            case.codex_home, "sessions", "2026", "09", "09", records.codex_rollout_name(session_id)
        ),
        records.codex_record(skills_root),
    )
    case.decoy = case.write_record(
        os.path.join(case.project, ".codex", "rollout.jsonl"), records.codex_decoy_record()
    )
    payload = records.codex_payload("SessionStart", case.project, case.decoy, session_id)
    case.run_hook("codex", payload)
    return case.run_feedback("codex", **(ANSWERS | answers))


def rate_opencode_session(case, **answers):
    """An opencode session: the plugin's own two module invocations, then `/fn-eval`.

    There is no record on disk to read, so the messages the plugin reads back
    over the SDK at the end of a turn are what carries usage, cost and tools.
    """
    case.git_identity()
    observe_opencode(case, "session.created")
    report_opencode_usage(case)
    return case.run_feedback("opencode", **(ANSWERS | answers))


USER_INSTRUCTIONS = "# how the user works\n"
PROJECT_INSTRUCTIONS = "# what this project is\n"


def write_instructions(case):
    """A user-level `CLAUDE.md`, and the project's `AGENTS.md` with `CLAUDE.md` linked to it."""
    case.write_file(os.path.join(case.home, ".claude", "CLAUDE.md"), USER_INSTRUCTIONS)
    agents = case.write_file(os.path.join(case.project, "AGENTS.md"), PROJECT_INSTRUCTIONS)
    os.symlink(agents, os.path.join(case.project, "CLAUDE.md"))


def observe_opencode(case, hook):
    """What the opencode plugin pipes to `agent_telemetry.hook` for one event."""
    payload = records.opencode_payload(hook, case.project)
    return case.run_module("hook", "opencode", stdin=json.dumps(payload))


def report_opencode_usage(case, messages=None):
    """What it pipes to `agent_telemetry.messages` at the end of every turn."""
    messages = records.opencode_messages() if messages is None else messages
    return case.run_module(
        "messages", "--session", records.SESSION_ID, stdin=json.dumps(messages)
    )
