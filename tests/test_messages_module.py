"""`python3 -m agent_telemetry.messages`: usage for an agent that keeps no record.

opencode has no transcript on disk to read, so its plugin reads the session's
messages back over the SDK at the end of every turn and pipes them here as one
JSON array. Only their token counts, their cost and the name of each tool part
are taken.

Driven by a plugin rather than a person, so like a hook it prints nothing and
exits 0 -- except when it is called wrong, which is the plugin's bug to see.
"""

import json

import flows
import harness
import records


class OpencodeMessages(harness.Sandboxed):
    def setUp(self):
        super().setUp()
        self.git_identity()
        flows.observe_opencode(self, "session.created")

    def test_usage_cost_and_tools_land_in_the_pending_document(self):
        run = flows.report_opencode_usage(self)
        self.assertEqual((run.code, run.out), (0, ""))
        document = self.pending(records.SESSION_ID)
        self.assertEqual(document["usage"], records.OPENCODE_USAGE)
        self.assertEqual(document["cost_usd"], records.OPENCODE_COST)
        self.assertEqual(document["tools"], records.OPENCODE_TOOLS)

    def test_the_messages_themselves_are_not_stored(self):
        flows.report_opencode_usage(self)
        self.assertNotIn(records.SENTINEL, json.dumps(self.pending(records.SESSION_ID)))

    def test_an_unrated_session_still_produces_no_result(self):
        flows.report_opencode_usage(self)
        self.assertEqual(self.results(), [])

    def test_a_session_rated_mid_turn_is_written_out_again(self):
        self.run_feedback("opencode", **flows.ANSWERS)
        self.assertEqual(self.one_result(records.SESSION_ID)["usage"], [])
        flows.report_opencode_usage(self)
        self.assertEqual(len(self.results()), 1)
        self.assertEqual(self.one_result(records.SESSION_ID)["usage"], records.OPENCODE_USAGE)

    def test_messages_for_a_session_never_observed_are_dropped(self):
        run = self.run_module(
            "messages", "--session", "never-seen", stdin=json.dumps(records.opencode_messages())
        )
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertIsNone(self.pending("never-seen"))

    def test_stdin_that_is_not_messages_is_dropped(self):
        run = self.run_module("messages", "--session", records.SESSION_ID, stdin="not json")
        self.assertEqual((run.code, run.out), (0, ""))
        self.assertEqual(self.pending(records.SESSION_ID)["usage"], [])

    def test_a_session_with_no_assistant_reply_reports_no_cost(self):
        flows.report_opencode_usage(self, messages=[])
        document = self.pending(records.SESSION_ID)
        self.assertEqual(document["usage"], [])
        self.assertIsNone(document["cost_usd"])

    def test_being_called_without_a_session_is_the_one_thing_it_reports(self):
        run = self.run_module("messages", stdin="[]")
        self.assertEqual(run.code, 2)
        self.assertIn("--session", run.err)
