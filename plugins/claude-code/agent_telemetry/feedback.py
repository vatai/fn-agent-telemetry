"""User feedback recorded alongside a session's telemetry.

Usage data says what a session did; it cannot say whether it was any good. This
module records the missing half: what the user was judging (`subject`), the
dimension they judged it on (`fom`), and a value. The answer is appended to the
session's own event log, so it carries the same `session_id` as every other
event and no join is ever needed.

Two kinds of figure of merit share one shape. Subjective ones are rated 1-5;
measured ones take whatever number the user actually observed, in that figure's
own unit. The figure decides the scale, and the scale is written onto the event,
so a mixed set of ratings and measurements stays readable without this table.

The vocabulary is fixed, since a free-form figure of merit would give N sessions
N incomparable metrics. Free wording goes in `comment`, never in `fom`.

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

RATING = {"min": 1, "max": 5, "integer": True, "unit": None, "better": "higher"}


def _measured(unit, better="higher", integer=False):
    """An open-ended scale: the user reports what they observed, in `unit`."""
    return {"min": 0, "max": None, "integer": integer, "unit": unit, "better": better}


FIGURES_OF_MERIT = {
    "satisfaction": {"rates": "how good the session was overall", "scale": RATING},
    "correctness": {"rates": "did the work come out right", "scale": RATING},
    "code_quality": {"rates": "readability and fit with the surrounding code", "scale": RATING},
    "autonomy": {"rates": "how little steering it needed", "scale": RATING},
    "trust": {"rates": "confidence in the result without re-checking it", "scale": RATING},
    "speedup": {"rates": "measured walltime, against the previous version", "scale": _measured("x")},
    "time_saved": {"rates": "minutes saved against doing it by hand", "scale": _measured("min")},
    "iterations": {
        "rates": "corrections needed before it was right",
        "scale": _measured("count", better="lower", integer=True),
    },
}

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


def scale_of(fom):
    return FIGURES_OF_MERIT[fom]["scale"]


def describe_scale(scale):
    """Human phrasing of a scale, for `--help` and for validation errors."""
    bound = f"{scale['min']}-{scale['max']}" if scale["max"] else f"{scale['min']} or more"
    unit = f" {scale['unit']}" if scale["unit"] else ""
    return f"{bound}{unit}, {scale['better']} is better"


def _build_event(args, transcript):
    normalized = {
        "event_type": EVENT_TYPE,
        "native_event": NATIVE_EVENT,
        "session_id": snapshot.session_id_for(transcript),
        "cwd": os.getcwd(),
        "transcript_path": transcript,
        "subject": args.subject,
        "fom": args.fom,
        "scale": dict(scale_of(args.fom)),
        "value": _plain(args.value),
        "comment": args.comment,
    }
    return events.build_event(AGENT, normalized, vars(args))


def _plain(value):
    """Keep whole numbers whole, so a rating reads as `4` rather than `4.0`."""
    return int(value) if float(value).is_integer() else value


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
    parser.add_argument("--value", required=True, type=float, help="scale depends on --fom")
    parser.add_argument("--comment", default=None, help="anything the scale cannot express")
    args = parser.parse_args(argv)
    _check_value(parser, args)
    return args


def _fom_help():
    return "; ".join(
        f"{name} [{describe_scale(fom['scale'])}]: {fom['rates']}"
        for name, fom in FIGURES_OF_MERIT.items()
    )


def _check_value(parser, args):
    """Validated against the chosen figure's own scale, not one fixed range."""
    scale = scale_of(args.fom)
    if scale["integer"] and not args.value.is_integer():
        parser.error(f"--value for {args.fom} must be a whole number")
    if not _within(args.value, scale):
        parser.error(f"--value for {args.fom} must be {describe_scale(scale)}")


def _within(value, scale):
    return value >= scale["min"] and (scale["max"] is None or value <= scale["max"])


if __name__ == "__main__":
    sys.exit(main())
