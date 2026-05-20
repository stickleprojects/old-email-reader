# old-email-reader (safe v1)

Safe, deterministic Lotus-style export parser + minimal CLI reader.

## What is implemented

- Conservative mixed-format record segmentation using long `*` delimiters.
- Robust message extraction with explicit support for:
  - header-style `From/To/cc/Subject/Body`
  - inline reply/forward metadata fallback
  - forwarded chain markers
  - blank subject/body
  - attachment marker extraction (`[attachment "..."]`)
  - noisy signature/disclaimer/banner cleanup in `body_clean`
- Dual preservation model:
  - raw record + raw field values
  - normalized field values
  - per-field extraction confidence + ambiguity/source flags
  - per-record warnings/errors
- Safe baseline threading:
  - grouped by normalized subject with conservative participant/time checks
  - ambiguity flags retained when grouping confidence is limited
  - no forced parent-child ancestry reconstruction
- Diagnostics output:
  - normalized JSON containing messages, conversations, and parse report
  - parse report includes records seen, messages parsed, skipped fragments, confidence distribution, ambiguity counts
- Minimal reader (CLI browse mode) with filters:
  - date start/end
  - from partial match against normalized sender
  - to partial match against normalized recipients
  - text search across subject + `body_clean` (optional raw inclusion)
  - deterministic ordering (conversations by `last_at` desc; messages by datetime asc then id)

## Intentionally deferred in v1

- Advanced parent-child thread ancestry reconstruction from quoted chains.
- ML/semantic disambiguation or risky deep inference.
- Rich UI (web/TUI styling and interaction polish).
- Full disclaimer/signature classifier coverage for all enterprises.

## Known risks and ambiguity points

- Some dates are only available inside inline quoted sections; these are marked inferred/ambiguous.
- Identity normalization is conservative and may not collapse all alias variants.
- Noise cleanup uses prefix rules; unknown disclaimer formats remain in `body_clean` to avoid accidental data loss.
- Conversation grouping is intentionally reversible and may over-group in edge cases sharing subject lines.

## How to run

From repository root:

```bash
python -m old_email_reader parse data/old_personal.txt --json-out /tmp/old_personal.normalized.json --report-out /tmp/old_personal.report.json
```

```bash
python -m old_email_reader browse data/old_personal.txt --date-start 2003-11-26 --date-end 2003-11-30 --from kieron --to suki --text chips
```

Search raw body text too:

```bash
python -m old_email_reader browse data/old_personal.txt --text "Forwarded" --include-raw
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

## Example parse report output

```json
{
  "records_seen": 5,
  "messages_parsed": 5,
  "skipped_unparsed_fragments": 0,
  "confidence_distribution": {
    "from_field:high": 4,
    "from_field:medium": 1
  },
  "ambiguity_counts": {
    "date_inferred_from_inline": 2
  },
  "conversation_count": 3
}
```

## Phase-2 recommendations

1. Add optional parent-link evidence graph (quoted sender/date references) with confidence scoring.
2. Improve identity canonicalization via configurable alias map.
3. Add richer noise classifier with explicit `removed_sections` output (still reversible).
4. Add cached parse index to speed browse/filter on large archives.
5. Add lightweight local web UI backed by the same reader/filter primitives.
