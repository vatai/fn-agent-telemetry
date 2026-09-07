"""User feedback recorded alongside a session's telemetry.

Usage data says what a session did; it cannot say whether it was any good. This
module records the missing half: what the user was judging (`subject`), the
figure of merit they judged it on (`fom`), the number they observed (`value`),
and one normalised score for the session overall (`satisfaction`). The answer is
appended to the session's own event log, so it carries the same `session_id` as
every other event and no join is ever needed.

The figure of merit is free text, because a useful one is domain-specific:
GFLOP/s for a kernel, samples/s for a training loop, x for an optimisation.
`SUGGESTED_FOMS` is what `/fn-eval` offers as a starting point, never a closed
set, and the unit arrives from the user together with the number.

Free text alone would give N sessions N incomparable metrics, which is what
`satisfaction` is for: the same 1-5 scale on every session, read as a normalised
figure of merit. A 100x speedup is a 5, a slowdown is a 1, whatever the figure
was measured in. So the domain metric stays honest and the cross-session axis
stays fixed. That is also where direction lives -- `loss` falls where `accuracy`
rises, and no lookup can tell which a free-form figure is -- so it is asked for
rather than inferred.

Unlike the hooks, this runs from a slash command the user typed, so a failure
here is worth printing rather than swallowing. The answer is written before the
archive is packed: a snapshot that fails should cost an archive, never a reply
a human just spent three turns giving.
"""

import argparse
import os
import sys

from . import adapters, events, paths, snapshot, writer

RATING = {"min": 1, "max": 5, "integer": True, "unit": None, "better": "higher"}

# What `/fn-eval` offers for its first question -- suggestions, not a
# vocabulary, since `--fom` accepts any name. Each plugin's command prompt
# mirrors this list, because a markdown prompt cannot import Python; dev-notes.md
# names all three places, so a figure added here gets added there too.
SUGGESTED_FOMS = (
    ("flops", "GFLOP/s", "numerical algorithms"),
    ("samples_per_sec", "samples/s", "ML throughput"),
    ("accuracy", None, "ML model quality"),
    ("loss", None, "ML training loss"),
    ("speedup", "x", "optimising existing code"),
    ("hours_saved", "h", "human effort spared on development"),
    ("text_quality", "1-5", "text generated for a paper"),
    ("plot_quality", "1-5", "plots generated for a paper"),
)

EVENT_TYPE = "feedback"
NATIVE_EVENT = "SlashCommand"


def main(argv=None):
    """Entry point for the manual `/fn-eval` command. Prints one status line."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    session_id, transcript = snapshot.resolve_session(os.getcwd(), args.agent)
    recorded = writer.append_event(_build_event(args, session_id, transcript))
    archive = snapshot.snapshot(session_id, transcript) if session_id else None
    print(_status(recorded, archive))
    return 0


def rated(session_id):
    """Whether `/fn-eval` has already recorded an answer for this session."""
    log = paths.log_path(session_id)
    if not log or not os.path.isfile(log):
        return False
    return any(event.get("event_type") == EVENT_TYPE for event in events.read_log(log))


def fom_scale(unit):
    """The scale of a free-form figure: whatever was observed, in `unit`.

    Open-ended and directionless, since neither bound nor direction can be
    looked up for a name nobody declared in advance. `unit` stays a key even
    when there is no unit to name, because a scale carrying no `unit` key at all
    is how the reader recognises a row written before measured figures existed.
    """
    return {"min": 0, "max": None, "integer": False, "unit": unit, "better": None}


def describe_scale(scale):
    """Human phrasing of a scale, for `--help` and for validation errors."""
    bound = f"{scale['min']}-{scale['max']}" if scale["max"] else f"{scale['min']} or more"
    unit = f" {scale['unit']}" if scale["unit"] else ""
    better = f", {scale['better']} is better" if scale["better"] else ""
    return f"{bound}{unit}{better}"


def _build_event(args, session_id, transcript):
    normalized = {
        "event_type": EVENT_TYPE,
        "native_event": NATIVE_EVENT,
        "session_id": session_id,
        "cwd": os.getcwd(),
        "transcript_path": transcript,
        "subject": args.subject,
        "fom": _fom_key(args.fom),
        "scale": fom_scale(args.unit),
        "value": _plain(args.value),
        "satisfaction": int(args.satisfaction),
        "satisfaction_scale": dict(RATING),
        "comment": args.comment,
    }
    return events.build_event(args.agent, normalized, vars(args))


def _fom_key(name):
    """One spelling per figure, so `Speed up` and `speed_up` group together."""
    return "_".join(name.strip().lower().split())


def _plain(value):
    """Keep whole numbers whole, so a count reads as `4` rather than `4.0`."""
    return int(value) if float(value).is_integer() else value


def _status(recorded, archive):
    if not recorded:
        return "feedback not recorded"
    if archive:
        return f"feedback recorded -> {archive}"
    return "feedback recorded, pending: no session found to archive it with"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="agent-telemetry-feedback")
    # Supplied by each plugin's own wrapper, never typed by whoever runs the
    # command: it selects which agent's events this session is looked up among.
    parser.add_argument("--agent", required=True, choices=adapters.known_agents())
    parser.add_argument("--subject", required=True, help="what was being judged")
    parser.add_argument("--fom", required=True, help=_fom_help())
    parser.add_argument("--unit", default=None, help="the figure of merit's unit, if it has one")
    parser.add_argument("--value", required=True, type=float, help="the number observed, in --unit")
    parser.add_argument(
        "--satisfaction",
        required=True,
        type=float,
        help=f"the session overall, as a normalised figure of merit [{describe_scale(RATING)}]",
    )
    parser.add_argument("--comment", default=None, help="anything the numbers cannot express")
    args = parser.parse_args(argv)
    _check_values(parser, args)
    return args


def _fom_help():
    suggested = ", ".join(name for name, _unit, _measures in SUGGESTED_FOMS)
    return f"what was measured; any name, the suggested ones being {suggested}"


def _check_values(parser, args):
    """Both numbers are checked here, since a rejected answer is re-asked for.

    The figure's own value can only be bounded below -- nobody declared its
    range -- so `--satisfaction` is the one that is genuinely validated, and it
    has to be, being the only field comparable across sessions.
    """
    scale = fom_scale(args.unit)
    if not _within(args.value, scale):
        parser.error(f"--value must be {describe_scale(scale)}")
    if not args.satisfaction.is_integer() or not _within(args.satisfaction, RATING):
        parser.error(f"--satisfaction must be {describe_scale(RATING)}")


def _within(value, scale):
    return value >= scale["min"] and (scale["max"] is None or value <= scale["max"])


if __name__ == "__main__":
    sys.exit(main())
