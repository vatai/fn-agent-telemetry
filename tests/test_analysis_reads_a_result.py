"""The document on disk is the interface between the two sides, so both sides run.

`analysis/` imports nothing from the plugins and no plugin install ships it, so
nothing but a written result connects them. These tests produce one with the
binaries and read it back with `analysis/archives.py`, which is the only check
that the two agree.

They also pin what a row leaves blank: a column that would otherwise claim a
zero for something the agent never reported.
"""

import flows
import harness
import records

from analysis import archives


class AClaudeCodeResult(harness.Sandboxed):
    def setUp(self):
        super().setUp()
        flows.rate_claude_session(self)
        self.row = archives.read(self.one_result_path())

    def one_result_path(self):
        self.assertEqual(len(self.results()), 1)
        return self.results()[0]

    def test_the_row_names_the_session_and_its_agent(self):
        self.assertEqual(self.row["format"], 4)
        self.assertEqual(self.row["agent"], "claude-code")
        self.assertEqual(self.row["session_id"], records.SESSION_ID)
        self.assertEqual(self.row["cwd"], "widget")
        self.assertEqual(self.row["email"], harness.ACCOUNT_EMAIL)

    def test_the_totals_are_the_rows_the_plugin_wrote(self):
        self.assertEqual(self.row["messages"], len(records.CLAUDE_USAGE))
        self.assertEqual(self.row["output"], sum(r["output"] for r in records.CLAUDE_USAGE))
        self.assertEqual(self.row["cost_usd"], records.CLAUDE_COST)
        self.assertEqual(self.row["models"], records.MODEL)

    def test_tool_and_skill_activity_survives_the_round_trip(self):
        self.assertEqual(self.row["tools"], len(records.CLAUDE_TOOLS))
        self.assertEqual(self.row["tool_calls"], 4)
        self.assertEqual(self.row["tool_names"], "Bash 2, Skill 2")
        self.assertEqual(self.row["skill_calls"], 2)
        self.assertEqual(self.row["skills_used"], f"code-review 1, {records.UNLISTED_SKILL} 1")

    def test_the_rating_reads_back_through_its_own_scale(self):
        self.assertEqual(self.row["fom"], "hours_saved")
        self.assertEqual(self.row["value"], 6)
        self.assertEqual(self.row["unit"], "h")
        self.assertEqual(self.row["satisfaction"], 5)
        self.assertFalse(self.row["legacy_scale"])

    def test_the_instructions_are_measured_not_reproduced(self):
        self.assertEqual(self.row["context_files"], 2)
        self.assertEqual(
            self.row["context_chars"],
            len(flows.USER_INSTRUCTIONS) + len(flows.PROJECT_INSTRUCTIONS),
        )


class ACodexResult(harness.Sandboxed):
    def setUp(self):
        super().setUp()
        flows.rate_codex_session(self)
        self.row = archives.read(self.results()[0])

    def test_what_codex_cannot_report_is_blank_and_not_zero(self):
        self.assertIsNone(self.row["cost_usd"])
        self.assertIsNone(self.row["skill_calls"])
        self.assertIsNone(self.row["skills_used"])

    def test_what_it_does_report_reads_back(self):
        self.assertEqual(self.row["agent"], "codex")
        self.assertEqual(self.row["messages"], len(records.CODEX_USAGE))
        self.assertEqual(self.row["tool_names"], "apply_patch 1, shell 1")
        self.assertEqual(self.row["models"], records.CODEX_MODEL)


class EveryResultInTheDirectory(harness.Sandboxed):
    def test_two_agents_results_sit_side_by_side_in_one_listing(self):
        flows.rate_claude_session(self)
        flows.rate_codex_session(self, session_id=records.OTHER_SESSION_ID)
        rows = archives.sessions(self.telemetry)
        self.assertEqual(sorted(row["agent"] for row in rows), ["claude-code", "codex"])
