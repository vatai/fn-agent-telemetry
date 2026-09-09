"""`bin/agent-telemetry-feedback`: the three answers in, one result file out.

This is the only thing that produces a result, so this is where a whole document
is asserted -- what each agent's own record yields, and what each agent cannot
say. The three wrappers are all run: they differ in how they find the shared
package, and in which agent's pending documents they look the session up among.

Unlike a hook, this runs from a command the user typed, so it reports what it
did on stdout and rejects an answer it cannot store.
"""

import json
import os

import flows
import harness
import records

ANSWERS = flows.ANSWERS

RECORDED = "feedback recorded -> "
NOT_RECORDED = "feedback not recorded: no session found to record it against"


class Rated(harness.Sandboxed):
    """A test case whose session has already been rated."""

    def result(self):
        return self.one_result(records.SESSION_ID)

    def assertReported(self, run):
        self.assertEqual(run.code, 0)
        self.assertTrue(run.out.startswith(RECORDED), run.out)
        self.assertEqual(run.out.strip()[len(RECORDED) :], self.results()[0])


class ClaudeCodeFeedback(Rated):
    """A rated Claude Code session, read out of its own transcript."""

    def setUp(self):
        super().setUp()
        self.rating = flows.rate_claude_session(self)

    def test_it_reports_the_file_it_wrote(self):
        self.assertReported(self.rating)

    def test_the_session_is_named_but_not_placed(self):
        session = self.result()["session"]
        self.assertEqual(session["session_id"], records.SESSION_ID)
        self.assertEqual(session["agent"], "claude-code")
        self.assertEqual(session["cwd"], "widget")
        self.assertEqual(session["host"]["user"], "tester")
        self.assertEqual(session["host"]["email"], harness.ACCOUNT_EMAIL)

    def test_it_carries_no_record_path(self):
        self.assertNotIn("_record_path", self.result())
        self.assertIn("_record_path", self.pending(records.SESSION_ID))

    def test_usage_is_one_row_per_message(self):
        self.assertEqual(self.result()["usage"], records.CLAUDE_USAGE)

    def test_the_cost_is_the_largest_reported_not_the_last(self):
        self.assertEqual(self.result()["cost_usd"], records.CLAUDE_COST)

    def test_tools_are_names_and_counts_deduped_by_call(self):
        self.assertEqual(self.result()["tools"], records.CLAUDE_TOOLS)

    def test_skills_fold_every_listing_and_count_their_uses(self):
        self.assertEqual(
            self.result()["skills"],
            [
                {
                    "name": "code-review",
                    "source": "listing",
                    "text": "Review the current diff for bugs",
                    "uses": 1,
                },
                {
                    "name": "fn-eval",
                    "source": "$PROJECTS/widget/.claude/commands/fn-eval.md",
                    "text": records.SKILL_TEXT,
                    "uses": 0,
                },
                {"name": records.UNLISTED_SKILL, "source": "invocation", "text": None, "uses": 1},
            ],
        )

    def test_the_instructions_are_carried_whole_with_their_paths_rewritten(self):
        self.assertEqual(
            self.result()["context"],
            [
                {
                    "path": "$HOME/.claude/CLAUDE.md",
                    "names": ["$HOME/.claude/CLAUDE.md"],
                    "text": flows.USER_INSTRUCTIONS,
                },
                {
                    "path": "$PROJECTS/widget/AGENTS.md",
                    "names": ["$PROJECTS/widget/AGENTS.md", "$PROJECTS/widget/CLAUDE.md"],
                    "text": flows.PROJECT_INSTRUCTIONS,
                },
            ],
        )

    def test_the_rating_is_stored_with_the_scale_it_was_given_on(self):
        feedback = self.result()["feedback"]
        self.assertEqual(feedback["subject"], ANSWERS["subject"])
        self.assertEqual(feedback["fom"], "hours_saved")
        self.assertEqual(feedback["value"], 6)
        self.assertEqual(feedback["scale"]["unit"], "h")
        self.assertEqual(feedback["satisfaction"], 5)
        self.assertEqual(feedback["satisfaction_scale"]["max"], 5)
        self.assertIsNone(feedback["comment"])

    def test_a_figure_of_merit_is_stored_under_one_spelling(self):
        self.run_feedback("claude-code", **(ANSWERS | {"fom": "Hours Saved"}))
        self.assertEqual(self.result()["feedback"]["fom"], "hours_saved")

    def test_rating_again_overwrites_the_sessions_own_file(self):
        again = self.run_feedback("claude-code", **(ANSWERS | {"satisfaction": 2}))
        self.assertEqual(again.out, self.rating.out)
        self.assertEqual(len(self.results()), 1)
        self.assertEqual(self.result()["feedback"]["satisfaction"], 2)

    def test_a_turn_ending_writes_nothing_out(self):
        """Claude Code's record holds nothing new until the session ends, which
        is when the cost lands -- so `Stop` is not one of its `FINALIZE_AT`."""
        first = self.result()["session"]["ended"]
        payload = records.claude_payload("Stop", self.project, self.record)
        self.assertEqual(self.run_hook("claude-code", payload).code, 0)
        self.assertEqual(self.result()["session"]["ended"], first)

    def test_session_end_writes_a_rated_session_out_again(self):
        first = self.result()["session"]["ended"]
        payload = records.claude_payload("SessionEnd", self.project, self.record)
        self.assertEqual(self.run_hook("claude-code", payload).code, 0)
        self.assertEqual(len(self.results()), 1)
        self.assertGreater(self.result()["session"]["ended"], first)


class CodexFeedback(Rated):
    """A rated codex session: cumulative usage, no cost, and no skill uses."""

    def setUp(self):
        super().setUp()
        self.rating = flows.rate_codex_session(self)

    def test_it_reports_the_file_it_wrote(self):
        self.assertReported(self.rating)

    def test_usage_is_what_each_cumulative_snapshot_grew_by(self):
        self.assertEqual(self.result()["usage"], records.CODEX_USAGE)

    def test_the_rollout_is_found_by_session_id_not_by_the_payloads_path(self):
        written = json.dumps(self.result())
        self.assertNotIn("someone-elses-model", written)
        self.assertNotIn("999999", written)

    def test_codex_reports_no_cost_at_all(self):
        self.assertIsNone(self.result()["cost_usd"])

    def test_tools_are_counted_over_both_call_shapes(self):
        self.assertEqual(self.result()["tools"], records.CODEX_TOOLS)

    def test_its_skills_have_text_on_disk_and_no_uses(self):
        self.assertEqual(
            self.result()["skills"],
            [
                {
                    "name": "fn-eval",
                    "source": "$HOME/.codex/skills/fn-eval/SKILL.md",
                    "text": records.SKILL_TEXT,
                },
                {
                    "name": "unpacked",
                    "source": "listing",
                    "text": "A skill with no file of its own",
                },
            ],
        )

    def test_a_turn_ending_writes_a_rated_session_out_again(self):
        """Codex's usage accumulates as the session runs and there is no cost to
        wait for, so every turn's end is worth writing out -- and `SessionEnd`
        is a hook it allows one second by default."""
        first = self.result()["session"]["ended"]
        payload = records.codex_payload("Stop", self.project, self.decoy)
        self.assertEqual(self.run_hook("codex", payload).code, 0)
        self.assertEqual(len(self.results()), 1)
        self.assertGreater(self.result()["session"]["ended"], first)

    def test_the_identity_falls_back_to_git(self):
        self.assertEqual(self.result()["session"]["host"]["email"], harness.GIT_EMAIL)


class OpencodeFeedback(Rated):
    """A rated opencode session, whose usage arrived over the SDK instead."""

    def setUp(self):
        super().setUp()
        self.rating = flows.rate_opencode_session(self)

    def test_it_reports_the_file_it_wrote(self):
        self.assertReported(self.rating)

    def test_usage_and_cost_come_from_the_messages(self):
        self.assertEqual(self.result()["usage"], records.OPENCODE_USAGE)
        self.assertEqual(self.result()["cost_usd"], records.OPENCODE_COST)

    def test_tools_are_counted_once_per_part(self):
        self.assertEqual(self.result()["tools"], records.OPENCODE_TOOLS)

    def test_it_publishes_no_skill_listing_to_collect(self):
        self.assertEqual(self.result()["skills"], [])


class RejectedAnswers(harness.Sandboxed):
    """What the command does with an answer it cannot store, so it can re-ask."""

    def setUp(self):
        super().setUp()
        record = os.path.join(self.root, "session.jsonl")
        self.write_record(record, records.claude_record())
        self.run_hook("claude-code", records.claude_payload("SessionStart", self.project, record))

    def assertRejected(self, expected, **answers):
        run = self.run_feedback("claude-code", **(ANSWERS | answers))
        self.assertEqual(run.code, 2)
        self.assertIn(expected, run.err)
        self.assertEqual(self.results(), [])

    def test_a_satisfaction_off_the_fixed_scale_is_rejected(self):
        self.assertRejected("--satisfaction must be 1-5", satisfaction=7)

    def test_a_satisfaction_that_is_not_a_whole_number_is_rejected(self):
        self.assertRejected("--satisfaction must be 1-5", satisfaction=4.5)

    def test_a_negative_figure_is_rejected(self):
        self.assertRejected("--value must be 0 or more", value=-1)

    def test_a_missing_answer_is_rejected(self):
        self.assertRejected("--fom", fom=None)

    def test_an_unknown_agent_is_rejected(self):
        run = self.run_module("feedback", "--agent", "vim", *harness.options(ANSWERS))
        self.assertEqual(run.code, 2)
        self.assertIn("--agent", run.err)


class NoSessionToRate(harness.Sandboxed):
    """`/fn-eval` typed where no session of this agent's was ever observed."""

    def test_nothing_is_recorded_and_nothing_fails(self):
        run = self.run_feedback("claude-code", **ANSWERS)
        self.assertEqual((run.code, run.out.strip()), (0, NOT_RECORDED))
        self.assertEqual(self.results(), [])

    def test_another_agents_session_is_not_this_ones(self):
        flows.observe_opencode(self, "session.created")
        run = self.run_feedback("claude-code", **ANSWERS)
        self.assertEqual((run.code, run.out.strip()), (0, NOT_RECORDED))
