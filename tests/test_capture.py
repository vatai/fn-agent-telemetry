"""The collection rules on their own, where running a wrapper would hide them.

Everything here is asserted end-to-end as well, through the binaries. These
tests exist for the cases a session cannot easily be built around: a record that
is missing or half-written, a project with no instructions above it, an output
name for a session that started at a particular moment.
"""

import datetime
import json
import os
from unittest import mock

import harness
import records

from agent_telemetry import context, paths, skills, usage


class InstructionsCollected(harness.Sandboxed):
    """`context.collect`: the `AGENTS.md` and `CLAUDE.md` in force, whole."""

    def user_dir(self):
        return self.make_directory(self.home, ".claude")

    def test_the_directories_above_the_project_are_collected_outermost_first(self):
        above = self.write_file(os.path.join(self.home, "code", "AGENTS.md"), "# above\n")
        here = self.write_file(os.path.join(self.project, "AGENTS.md"), "# here\n")
        collected = context.collect(self.project)
        self.assertEqual([entry["path"] for entry in collected], [above, here])

    def test_one_file_reached_by_both_names_is_one_entry(self):
        agents = self.write_file(os.path.join(self.project, "AGENTS.md"), "# both\n")
        link = os.path.join(self.project, "CLAUDE.md")
        os.symlink(agents, link)
        collected = context.collect(self.project)
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0]["path"], agents)
        self.assertEqual(collected[0]["names"], [agents, link])

    def test_the_user_level_files_come_before_the_project_ones(self):
        user = self.write_file(os.path.join(self.user_dir(), "CLAUDE.md"), "# user\n")
        here = self.write_file(os.path.join(self.project, "AGENTS.md"), "# here\n")
        collected = context.collect(self.project, [self.user_dir()])
        self.assertEqual([entry["path"] for entry in collected], [user, here])

    def test_a_session_with_no_directory_collects_only_the_user_files(self):
        user = self.write_file(os.path.join(self.user_dir(), "CLAUDE.md"), "# user\n")
        collected = context.collect(None, [self.user_dir()])
        self.assertEqual([entry["path"] for entry in collected], [user])

    def test_directories_with_nothing_in_them_are_not_an_error(self):
        missing = os.path.join(self.root, "not-a-directory")
        self.assertEqual(context.collect(self.project, [missing]), [])


class UsageFromARecord(harness.Sandboxed):
    """`usage.from_claude_record`: the numbers, and what their absence means."""

    def record(self, lines):
        return self.write_file(os.path.join(self.root, "session.jsonl"), lines)

    def test_a_record_with_no_cost_reports_none_rather_than_zero(self):
        without_cost = [r for r in records.claude_record() if r.get("type") != "cost-state"]
        path = self.write_record(os.path.join(self.root, "session.jsonl"), without_cost)
        rows, cost = usage.from_claude_record(path)
        self.assertEqual(rows, records.CLAUDE_USAGE)
        self.assertIsNone(cost)

    def test_a_record_that_is_not_there_yields_nothing(self):
        gone = os.path.join(self.root, "gone.jsonl")
        self.assertEqual(usage.from_claude_record(gone), ([], None))
        self.assertEqual(usage.from_claude_record(None), ([], None))

    def test_a_half_written_last_line_is_skipped_not_fatal(self):
        whole = json.dumps(records.claude_record()[2])
        path = self.record(whole + "\n" + whole[: len(whole) // 2])
        rows, _cost = usage.from_claude_record(path)
        self.assertEqual([row["message_id"] for row in rows], ["msg_1"])


class SkillsFromARecord(harness.Sandboxed):
    """`skills.from_*_record`: what a session was told it had available."""

    def test_a_claude_record_with_no_listing_has_no_skills(self):
        without = [r for r in records.claude_record() if "attachment" not in r]
        path = self.write_record(os.path.join(self.root, "session.jsonl"), without)
        self.assertEqual(skills.from_claude_record(path, self.project), [])

    def test_a_codex_rollout_old_enough_to_publish_none_has_no_skills(self):
        without = [r for r in records.codex_record("/skills") if r.get("type") != "world_state"]
        path = self.write_record(os.path.join(self.root, "rollout.jsonl"), without)
        self.assertEqual(skills.from_codex_record(path, self.project), [])


class OutputNames(harness.Sandboxed):
    """`paths`: where a document goes, and what it is called."""

    def setUp(self):
        super().setUp()
        patched = mock.patch.dict(os.environ, {paths.TELEMETRY_DIR_ENV: self.telemetry})
        patched.start()
        self.addCleanup(patched.stop)

    def test_a_result_is_named_for_when_the_session_started(self):
        started = datetime.datetime(2026, 9, 4, 16, 48, 32)
        path = paths.output_path(records.SESSION_ID, started)
        self.assertEqual(os.path.dirname(path), self.telemetry)
        self.assertEqual(os.path.basename(path), f"20260904-164832-{records.SESSION_ID}.json")

    def test_a_pending_document_is_named_for_the_session_alone(self):
        expected = os.path.join(self.telemetry, ".pending", records.SESSION_ID + ".json")
        self.assertEqual(paths.pending_path(records.SESSION_ID), expected)

    def test_a_session_id_that_is_not_a_filename_is_reduced_to_one(self):
        """An id comes from the agent, so a path in one must not become a path here."""
        path = paths.pending_path("../../etc/passwd")
        self.assertEqual(os.path.basename(path), "_.._etc_passwd.json")
        self.assertEqual(os.path.dirname(path), os.path.join(self.telemetry, ".pending"))
