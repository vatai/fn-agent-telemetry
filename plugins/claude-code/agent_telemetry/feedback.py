"""User feedback recorded alongside a session's telemetry.

Usage data says what a session did; it cannot say whether it was any good. This
module records the missing half: what the user was judging (`subject`), the
dimension they judged it on (`fom`), and a score. The answer is appended to the
session's own event log, so it carries the same `session_id` as every other
event and no join is ever needed.

Scores are only comparable because the vocabulary is fixed: every figure of
merit below is rated on the same scale, where the maximum is always best.
Free-form wording goes in `comment`, never in `fom`.

Unlike the hooks, this runs from a slash command the user typed, so a failure
here is worth printing rather than swallowing. The answer is written before the
archive is packed: a snapshot that fails should cost an archive, never a reply
a human just spent two turns giving.
"""

import argparse
import os
import sys

from . import events, snapshot, writer
from .adapters.claude_code import AGENT

FIGURES_OF_MERIT = {
    "correctness": "did the work come out right",
    "time_saved": "faster than doing it by hand",
    "few_iterations": "how close to right on the first try",
    "code_quality": "readability and fit with the surrounding code",
    "autonomy": "how little steering it needed",
    "trust": "confidence in the result without re-checking it",
}

SCALE = {"min": 1, "max": 5, "better": "higher"}

EVENT_TYPE = "feedback"
NATIVE_EVENT = "SlashCommand"


def main(argv=None):
    """Entry point for the manual `/fn-eval` command. Prints one status line."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    transcript = snapshot.resolve_transcript(os.getcwd())
    recorded = writer.append_event(_build_event(args, transcript))
    archive = snapshot.snapshot(transcript) if transcript else None
    print(_status(recorded, archive))
    return 0


def _build_event(args, transcript):
    normalized = {
        "event_type": EVENT_TYPE,
        "native_event": NATIVE_EVENT,
        "session_id": snapshot.session_id_for(transcript),
        "cwd": os.getcwd(),
        "transcript_path": transcript,
        "subject": args.subject,
        "fom": args.fom,
        "scale": dict(SCALE),
        "value": args.value,
        "comment": args.comment,
    }
    return events.build_event(AGENT, normalized, vars(args))


def _status(recorded, archive):
    if not recorded:
        return "feedback not recorded"
    if archive:
        return f"feedback recorded -> {archive}"
    return "feedback recorded, pending: no transcript found to archive it with"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-telemetry-feedback")
    parser.add_argument("--subject", required=True, help="what was being judged")
    parser.add_argument("--fom", required=True, choices=sorted(FIGURES_OF_MERIT), help=_fom_help())
    parser.add_argument("--value", required=True, type=_score, help=_score_help())
    parser.add_argument("--comment", default=None, help="anything the scale cannot express")
    return parser.parse_args(argv)


def _fom_help():
    return "; ".join(f"{name}: {meaning}" for name, meaning in FIGURES_OF_MERIT.items())


def _score_help():
    return f"{SCALE['min']}-{SCALE['max']}, where {SCALE['max']} is best"


def _score(text):
    value = int(text)
    if not SCALE["min"] <= value <= SCALE["max"]:
        raise argparse.ArgumentTypeError(_score_help())
    return value


if __name__ == "__main__":
    sys.exit(main())
