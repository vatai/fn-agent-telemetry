#!/usr/bin/env python3
"""Report on the collected telemetry.

    python3 analysis/report.py                  # a table to read
    python3 analysis/report.py --format csv     # every field, for analysis elsewhere
    python3 analysis/report.py --format json

The table is a readable subset; `csv` and `json` carry the whole row, so a
cross-session aggregate is a group-by over the export rather than a mode here.

`skills` is how many the session had available, with the number whose defining
text was found on disk in brackets -- most skills are built into the CLI and have
only their one-line description. `ctx` is how many `AGENTS.md`/`CLAUDE.md` files
were in effect.

The `fom` column is that session's own figure of merit and unit, which do not
compare across sessions; `sat` is the 1-5 normalisation of it that does. A value
marked `!` was rated against a scale that predates measured figures. A blank cost
means none was recorded, which is not a zero. Tokens are split the way they are
charged: `in`, `cache r`, `cache w` and `out` add up to `total`, while `think` is
the thinking part of `out` and so is already inside it.

A row from a `.zip` predates skill and context collection, so those columns are
blank for it; `archives.py` explains why those archives are still read.
"""

import argparse
import csv
import json
import sys

import archives

COLUMNS = (
    ("started", lambda row: (row["started"] or "")[:16].replace("T", " ")),
    ("agent", lambda row: row["agent"] or "?"),
    ("session", lambda row: (row["session_id"] or "?")[:12]),
    ("secs", lambda row: _number(row["duration_s"])),
    ("msgs", lambda row: str(row["messages"])),
    ("skills", lambda row: _skills(row)),
    ("ctx", lambda row: _number(row["context_files"])),
    ("in", lambda row: _tokens(row["input"])),
    ("cache r", lambda row: _tokens(row["cache_read"])),
    ("cache w", lambda row: _tokens(row["cache_write"])),
    ("out", lambda row: _tokens(row["output"])),
    ("think", lambda row: _tokens(row["reasoning"])),
    ("total", lambda row: _tokens(row["total"])),
    ("cost", lambda row: _cost(row["cost_usd"])),
    ("fom", lambda row: _fom(row)),
    ("sat", lambda row: _number(row["satisfaction"])),
    ("subject", lambda row: (row["subject"] or "")[:40]),
)


def main(argv=None):
    args = _parse_args(argv)
    rows = archives.sessions(args.dir)
    if not rows:
        print(f"nothing collected in {args.dir or archives.telemetry_dir()}", file=sys.stderr)
        return 1
    _writers()[args.format](rows)
    return 0


def _writers():
    return {"table": _write_table, "csv": _write_csv, "json": _write_json}


def _write_table(rows):
    lines = [[header for header, _ in COLUMNS]]
    lines += [[render(row) for _, render in COLUMNS] for row in rows]
    widths = [max(len(line[i]) for line in lines) for i in range(len(COLUMNS))]
    for line in lines:
        print("  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip())
    print()
    print(_summary(rows))


def _write_csv(rows):
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)


def _write_json(rows):
    json.dump(rows, sys.stdout, indent=2)
    print()


def _summary(rows):
    agents = sorted({row["agent"] or "?" for row in rows})
    rated = [row for row in rows if row["fom"]]
    costed = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    return (
        f"{len(rows)} sessions ({', '.join(agents)}), {len(rated)} rated, "
        f"{sum(row['total'] for row in rows):,} tokens, "
        f"${sum(costed):.2f} over the {len(costed)} with a cost recorded"
    )


def _skills(row):
    """Available, and how many had a defining file rather than a description."""
    if row["skills"] is None:
        return ""
    return f"{row['skills']} ({row['skills_with_text']})"


def _tokens(count):
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


def _cost(cost):
    return f"${cost:.2f}" if cost is not None else ""


def _number(value):
    return "" if value is None else f"{value:g}"


def _fom(row):
    """The session's own figure of merit; `sat` is the comparable column."""
    if not row["fom"]:
        return ""
    unit = row["unit"] or ""
    return f"{row['fom']}={_number(row['value'])}{unit}{'!' if row['legacy_scale'] else ''}"


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=None, help="telemetry directory [$AGENT_TELEMETRY_DIR]")
    parser.add_argument("--format", default="table", choices=sorted(_writers()))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
