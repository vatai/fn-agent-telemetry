#!/usr/bin/env python3
"""Report on the collected telemetry archives.

    python3 analysis/report.py                  # a table to read
    python3 analysis/report.py --format csv     # every field, for analysis elsewhere
    python3 analysis/report.py --format json

The table is a readable subset; `csv` and `json` carry the whole row, so a
cross-session aggregate is a group-by over the export rather than a mode here.

A value marked `!` was rated against a scale that predates the current
vocabulary and cannot be compared with today's, and a blank cost means the agent
archived none -- neither is a zero. See `archives.py` for why.
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
    ("prompts", lambda row: str(row["prompts"])),
    ("turns", lambda row: str(row["turns"])),
    ("tools", lambda row: _tools(row)),
    ("in", lambda row: _tokens(row["input"] + row["cache_read"] + row["cache_write"])),
    ("out", lambda row: _tokens(row["output"])),
    ("cost", lambda row: _cost(row["cost_usd"])),
    ("rating", lambda row: _rating(row)),
    ("subject", lambda row: (row["subject"] or "")[:40]),
)


def main(argv=None):
    args = _parse_args(argv)
    rows = archives.sessions(args.dir)
    if not rows:
        print(f"no archives in {args.dir or archives.telemetry_dir()}", file=sys.stderr)
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
        f"{sum(row['output'] for row in rows):,} output tokens, "
        f"${sum(costed):.2f} over the {len(costed)} with a cost recorded"
    )


def _tools(row):
    unfinished = row["tools_unfinished"]
    return f"{row['tools']}+{unfinished}?" if unfinished else str(row["tools"])


def _tokens(count):
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


def _cost(cost):
    return f"${cost:.2f}" if cost is not None else ""


def _number(value):
    return "" if value is None else f"{value:g}"


def _rating(row):
    if not row["fom"]:
        return ""
    unit = row["unit"] or ""
    return f"{row['fom']}={_number(row['value'])}{unit}{'!' if row['legacy_scale'] else ''}"


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=None, help="archive directory [$AGENT_TELEMETRY_DIR]")
    parser.add_argument("--format", default="table", choices=sorted(_writers()))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
