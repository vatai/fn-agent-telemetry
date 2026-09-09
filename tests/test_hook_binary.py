"""`bin/agent-telemetry-hook`: one native hook payload in, one document changed.

What a hook does is note that a session exists and snapshot the instructions it
is running under. It prints nothing, always exits 0, and produces no result --
that is `/fn-eval`'s job, tested in `test_feedback_binary.py`.

The claude-code and codex wrappers are both run here, because they resolve the
shared package differently: one through `CLAUDE_PLUGIN_ROOT` with a fallback to
its own location, the other relative to its own file only.
"""

import json
import os

import harness
import records

DEGENERATE_STDIN = ("", "   \n", "not json at all", "[]", '"just a string"', "{")


class ClaudeCodeHook(harness.Sandboxed):
    def setUp(self):
        super().setUp()
        self.record = self.write_record(
            os.path.join(self.home, ".claude", "projects", "widget", "session.jsonl"),
            records.claude_record(),
        )

    def hook(self, event, **kwargs):
        payload = records.claude_payload(event, self.project, self.record)
        return self.run_hook("claude-code", payload, **kwargs)

    def test_session_start_writes_a_pending_document_and_nothing_else(self):
        run = self.hook("SessionStart")
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertEqual(self.results(), [])
        document = self.pending(records.SESSION_ID)
        self.assertEqual(document["schema_version"], 4)
        self.assertEqual(document["session"]["session_id"], records.SESSION_ID)
        self.assertEqual(document["session"]["agent"], "claude-code")
        self.assertEqual(document["session"]["cwd"], self.project)
        self.assertEqual(document["_record_path"], self.record)

    def test_a_session_starts_with_nothing_collected_and_no_rating(self):
        self.hook("SessionStart")
        document = self.pending(records.SESSION_ID)
        self.assertEqual(document["skills"], [])
        self.assertEqual(document["tools"], [])
        self.assertEqual(document["usage"], [])
        self.assertIsNone(document["cost_usd"])
        self.assertIsNone(document["feedback"])

    def test_the_payload_is_read_for_four_fields_and_discarded(self):
        self.hook("Stop")
        stored = json.dumps(self.pending(records.SESSION_ID))
        self.assertNotIn(records.SENTINEL, stored)
        for dropped in ("prompt", "last_assistant_message", "tool_input", "tool_response"):
            self.assertNotIn(dropped, stored)

    def test_the_instructions_in_force_are_snapshotted(self):
        self.write_file(os.path.join(self.home, ".claude", "CLAUDE.md"), "# user\n")
        project_file = self.write_file(os.path.join(self.project, "AGENTS.md"), "# project\n")
        link = os.path.join(self.project, "CLAUDE.md")
        os.symlink(project_file, link)
        self.hook("SessionStart")
        collected = self.pending(records.SESSION_ID)["context"]
        self.assertEqual([entry["text"] for entry in collected], ["# user\n", "# project\n"])
        self.assertEqual(collected[1]["names"], [project_file, link])

    def test_a_turn_end_records_that_the_session_was_still_running(self):
        self.hook("SessionStart")
        started = self.pending(records.SESSION_ID)["session"]
        self.hook("Stop")
        ended = self.pending(records.SESSION_ID)["session"]
        self.assertEqual(ended["started"], started["started"])
        self.assertGreater(ended["ended"], started["ended"])

    def test_an_event_that_is_not_lifecycle_changes_nothing(self):
        self.hook("SessionStart")
        before = self.pending(records.SESSION_ID)
        run = self.hook("PreToolUse")
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertEqual(self.pending(records.SESSION_ID), before)

    def test_an_unrated_session_produces_no_result(self):
        self.hook("SessionStart")
        self.hook("SessionEnd")
        self.assertEqual(self.results(), [])
        self.assertIsNotNone(self.pending(records.SESSION_ID))

    def test_stdin_that_is_not_a_payload_is_dropped(self):
        for stdin in DEGENERATE_STDIN:
            with self.subTest(stdin=stdin):
                run = self.run_raw_hook("claude-code", stdin)
                self.assertEqual((run.code, run.out), (0, ""))
                self.assertIsNone(self.pending(records.SESSION_ID))
                self.assertEqual(self.results(), [])

    def test_it_finds_its_package_without_claude_plugin_root(self):
        run = self.hook("SessionStart", env=self.env(CLAUDE_PLUGIN_ROOT=None))
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertIsNotNone(self.pending(records.SESSION_ID))

    def test_a_telemetry_directory_it_cannot_create_is_not_an_error(self):
        blocked = self.write_file(os.path.join(self.root, "a-file"), "not a directory\n")
        run = self.hook("SessionStart", env=self.env(AGENT_TELEMETRY_DIR=blocked + "/under-it"))
        self.assertEqual((run.code, run.out, run.err), (0, "", ""))

    def test_an_unusable_agent_name_is_a_silent_no_op(self):
        payload = records.claude_payload("SessionStart", self.project, self.record)
        for args in ((), ("no-such-agent",)):
            with self.subTest(args=args):
                run = self.run_module("hook", *args, stdin=json.dumps(payload))
                self.assertEqual((run.code, run.out), (0, ""))
                self.assertIsNone(self.pending(records.SESSION_ID))


class CodexHook(harness.Sandboxed):
    def setUp(self):
        super().setUp()
        rollout = os.path.join(self.codex_home, "sessions", "2026", "09", "09")
        self.record = self.write_record(
            os.path.join(rollout, records.codex_rollout_name()),
            records.codex_record(os.path.join(self.codex_home, "skills")),
        )

    def hook(self, event, **kwargs):
        payload = records.codex_payload(event, self.project, self.record)
        return self.run_hook("codex", payload, **kwargs)

    def test_session_start_notes_a_codex_session(self):
        run = self.hook("SessionStart")
        self.assertEqual((run.code, run.out), (0, ""))
        document = self.pending(records.SESSION_ID)
        self.assertEqual(document["session"]["agent"], "codex")
        self.assertEqual(document["session"]["cwd"], self.project)
        self.assertEqual(document["_record_path"], self.record)

    def test_the_payload_is_read_for_four_fields_and_discarded(self):
        self.hook("Stop")
        self.assertNotIn(records.SENTINEL, json.dumps(self.pending(records.SESSION_ID)))

    def test_codex_reads_the_users_instructions_from_its_own_home(self):
        self.write_file(os.path.join(self.codex_home, "AGENTS.md"), "# codex user\n")
        self.write_file(os.path.join(self.home, ".claude", "CLAUDE.md"), "# not codex\n")
        self.hook("SessionStart")
        collected = self.pending(records.SESSION_ID)["context"]
        self.assertEqual([entry["text"] for entry in collected], ["# codex user\n"])

    def test_stdin_that_is_not_a_payload_is_dropped(self):
        run = self.run_raw_hook("codex", "not json at all")
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertIsNone(self.pending(records.SESSION_ID))
