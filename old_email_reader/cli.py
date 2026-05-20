from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from .parser import parse_file, write_json
from .reader import build_browse_rows


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Invalid date format: {value}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe v1 Lotus archive parser and reader")
    sub = parser.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse archive and emit normalized JSON")
    parse_cmd.add_argument("input_file", help="Path to archive export text")
    parse_cmd.add_argument("--json-out", required=True, help="Output JSON path")
    parse_cmd.add_argument("--report-out", help="Optional parse report JSON path")

    browse_cmd = sub.add_parser("browse", help="Browse parsed archive with filters")
    browse_cmd.add_argument("input_file", help="Path to archive export text")
    browse_cmd.add_argument("--date-start", help="Inclusive start date YYYY-MM-DD")
    browse_cmd.add_argument("--date-end", help="Inclusive end date YYYY-MM-DD")
    browse_cmd.add_argument("--from", dest="from_filter", help="Partial match against normalized sender")
    browse_cmd.add_argument("--to", dest="to_filter", help="Partial match against normalized recipients")
    browse_cmd.add_argument("--text", help="Text search across subject + clean body")
    browse_cmd.add_argument("--include-raw", action="store_true", help="Include raw body text in search scope")
    browse_cmd.add_argument("--limit", type=int, default=20, help="Maximum conversations to print")

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse":
        result = parse_file(args.input_file)
        write_json(result, args.json_out)
        if args.report_out:
            with open(args.report_out, "w", encoding="utf-8") as fh:
                json.dump(result.report, fh, indent=2, sort_keys=True)
        print(json.dumps(result.report, indent=2, sort_keys=True))
        return 0

    if args.command == "browse":
        result = parse_file(args.input_file)
        rows = build_browse_rows(
            result,
            date_start=_parse_date(args.date_start),
            date_end=_parse_date(args.date_end),
            from_contains=args.from_filter,
            to_contains=args.to_filter,
            text_query=args.text,
            include_raw=args.include_raw,
        )
        for row in rows[: args.limit]:
            print(f"[{row['conversation_id']}] {row['subject']} ({row['message_count']} messages)")
            print(f"  first={row['first_at']} last={row['last_at']} ambiguities={','.join(row['ambiguity_flags']) or 'none'}")
            for msg in row["messages"]:
                print(f"  - {msg['message_id']} date={msg['date']} from={msg['from']} to={msg['to']}")
                print(f"    subject={msg['subject']!r}")
                print(f"    preview={msg['preview']}")
            print()
        print(f"conversations_shown={min(len(rows), args.limit)} total_matching={len(rows)}")
        print(json.dumps(result.report, indent=2, sort_keys=True))
        return 0

    parser.error("Unknown command")
    return 2
