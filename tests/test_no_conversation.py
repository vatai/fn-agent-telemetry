"""Nothing written may carry conversation, whatever the inputs carried.

Every conversation-bearing field of every example input holds one sentinel
string: the prompt and the assistant's whole reply in a hook payload, a tool's
input and its result, an assistant record's text, a codex call's arguments, an
opencode part's output. A whole rated session is produced for each agent, and
then every byte under the telemetry directory -- results and pending documents
alike -- is required not to contain it.

This is the specification's own claim rather than one field's behaviour, which
is why it is tested once, at the outside, in the terms the claim is made in.
"""

import json

import flows
import harness
import records

# Everything a Claude Code session can fire, including the events that carry
# the most: a whole prompt, a whole reply, a tool's input and its result.
EVERY_EVENT = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SubagentStop",
    "PreCompact",
    "Notification",
    "SessionEnd",
)


class NoConversationIsCollected(harness.Sandboxed):
    def assertNothingCollectedCarriesIt(self):
        collected = self.everything_collected()
        self.assertTrue(collected.strip(), "nothing was collected, so nothing was checked")
        self.assertNotIn(records.SENTINEL, collected)

    def test_a_rated_claude_code_session(self):
        flows.rate_claude_session(self)
        self.assertIn(records.SENTINEL, harness.text(self.record))
        self.assertNothingCollectedCarriesIt()

    def test_a_rated_codex_session(self):
        flows.rate_codex_session(self)
        self.assertIn(records.SENTINEL, harness.text(self.record))
        self.assertNothingCollectedCarriesIt()

    def test_a_rated_opencode_session(self):
        flows.rate_opencode_session(self)
        self.assertIn(records.SENTINEL, json.dumps(records.opencode_messages()))
        self.assertNothingCollectedCarriesIt()

    def test_every_hook_event_a_session_can_fire(self):
        record = self.write_record(self.root + "/session.jsonl", records.claude_record())
        for event in EVERY_EVENT:
            payload = records.claude_payload(event, self.project, record)
            self.assertEqual(self.run_hook("claude-code", payload).code, 0)
        self.assertNothingCollectedCarriesIt()

    def test_the_opencode_events_its_plugin_reports(self):
        for hook in ("session.created", "session.idle", "session.deleted"):
            self.assertEqual(flows.observe_opencode(self, hook).code, 0)
        flows.report_opencode_usage(self)
        self.assertNothingCollectedCarriesIt()
