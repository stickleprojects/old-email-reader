from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import json
import re
from typing import Iterable

from .models import Conversation, ExtractedField, MessageRecord, ParseResult
from .normalizers import normalize_identities, normalize_identity, normalize_subject, parse_datetime

DELIMITER_RE = re.compile(r"^\*{30,}\s*$")
HEADER_RE = re.compile(r"^(From|To|cc|Subject|Body):\s*(.*)$", flags=re.IGNORECASE)
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?$")
ATTACHMENT_RE = re.compile(r"\[attachment\s+\"([^\"]+)\"[^\]]*\]", flags=re.IGNORECASE)
FORWARD_MARKER_RE = re.compile(r"-{2,}\s*(Forwarded by|Original Message)\b", flags=re.IGNORECASE)

NOISE_PREFIXES = (
    "Donovan Data Systems Ltd",
    "Tel :",
    "Fax :",
    "http://",
    "https://",
    "This e-mail",
    "This email",
    "Virus",
)


def segment_records(raw_text: str) -> list[tuple[int, int, str]]:
    records: list[tuple[int, int, str]] = []
    current_lines: list[str] = []
    start_line = 1
    for i, line in enumerate(raw_text.splitlines(), start=1):
        if DELIMITER_RE.match(line):
            if current_lines:
                records.append((start_line, i - 1, "\n".join(current_lines).rstrip("\n")))
                current_lines = []
            start_line = i + 1
        else:
            current_lines.append(line)
    if current_lines:
        records.append((start_line, len(raw_text.splitlines()), "\n".join(current_lines).rstrip("\n")))
    return [r for r in records if r[2].strip()]


def _extract_header_fields(lines: list[str]) -> tuple[dict[str, str], int]:
    headers: dict[str, str] = {}
    body_start_idx = 0
    for idx, line in enumerate(lines):
        match = HEADER_RE.match(line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip()
        headers[key] = value
        if key == "body":
            body_start_idx = idx + 1
            break
    return headers, body_start_idx


def _extract_inline_metadata(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    date_idx = None
    for idx, line in enumerate(lines):
        if DATE_RE.match(line.strip()):
            date_idx = idx
            result["date"] = line.strip()
            break
    if date_idx is not None:
        for back in range(date_idx - 1, -1, -1):
            candidate = lines[back].strip()
            if candidate:
                result["from"] = candidate
                break

        section: str | None = None
        bucket: dict[str, list[str]] = {"to": [], "cc": [], "subject": []}
        for idx in range(date_idx + 1, min(len(lines), date_idx + 40)):
            text = lines[idx].strip()
            if text.lower() in bucket:
                section = text.lower()
                continue
            if not text:
                if section == "subject" and bucket["subject"]:
                    break
                continue
            if section:
                bucket[section].append(text)

        for k, values in bucket.items():
            if values:
                result[k] = " ".join(values)
    return result


def _extract_attachments(raw_record: str) -> list[str]:
    attachments = ATTACHMENT_RE.findall(raw_record)
    deduped: list[str] = []
    seen = set()
    for item in attachments:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _clean_body(body_raw: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    cleaned: list[str] = []
    removed = 0
    for line in body_raw.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in NOISE_PREFIXES):
            removed += 1
            continue
        cleaned.append(line)
    if removed:
        warnings.append(f"noise_lines_removed:{removed}")
    return "\n".join(cleaned).strip(), warnings


def _field(raw: str, normalized: object, confidence: float, ambiguous: bool, source: str) -> ExtractedField:
    return ExtractedField(raw=raw, normalized=normalized, confidence=confidence, ambiguous=ambiguous, source=source)


def parse_record(record_text: str, record_index: int, start_line: int, end_line: int) -> MessageRecord:
    lines = record_text.splitlines()
    headers, body_start_idx = _extract_header_fields(lines)
    body_raw = "\n".join(lines[body_start_idx:]).strip() if body_start_idx else record_text.strip()
    inline = _extract_inline_metadata(lines)

    warnings: list[str] = []
    ambiguity_flags: list[str] = []

    raw_from = headers.get("from", "") or inline.get("from", "")
    from_source = "header" if headers.get("from", "") else ("inline" if inline.get("from", "") else "missing")
    from_ambiguous = from_source == "inline"
    if from_ambiguous:
        ambiguity_flags.append("from_inferred_from_inline")
    from_norm = normalize_identity(raw_from) if raw_from else ""
    from_conf = 0.95 if from_source == "header" and raw_from else (0.55 if raw_from else 0.0)

    raw_to = headers.get("to", "") or inline.get("to", "")
    to_source = "header" if headers.get("to", "") else ("inline" if inline.get("to", "") else "missing")
    to_ambiguous = to_source == "inline"
    if to_ambiguous:
        ambiguity_flags.append("to_inferred_from_inline")
    to_norm = normalize_identities(raw_to)
    to_conf = 0.95 if to_source == "header" and raw_to else (0.55 if raw_to else 0.0)

    raw_cc = headers.get("cc", "") or inline.get("cc", "")
    cc_source = "header" if headers.get("cc", "") else ("inline" if inline.get("cc", "") else "missing")
    cc_ambiguous = cc_source == "inline"
    if cc_ambiguous:
        ambiguity_flags.append("cc_inferred_from_inline")
    cc_norm = normalize_identities(raw_cc)
    cc_conf = 0.95 if cc_source == "header" and raw_cc else (0.55 if raw_cc else 0.0)

    raw_subject = headers.get("subject", "") or inline.get("subject", "")
    subject_source = "header" if "subject" in headers else ("inline" if inline.get("subject", "") else "missing")
    subject_ambiguous = subject_source == "inline"
    if subject_ambiguous:
        ambiguity_flags.append("subject_inferred_from_inline")
    if not raw_subject.strip():
        warnings.append("blank_subject")
    subject_norm = normalize_subject(raw_subject)
    subject_conf = 0.95 if subject_source == "header" and raw_subject.strip() else (0.55 if raw_subject else 0.0)

    raw_date = inline.get("date", "")
    date_source = "inline" if raw_date else "missing"
    parsed_dt = parse_datetime(raw_date)
    date_ambiguous = date_source == "inline"
    if date_ambiguous:
        ambiguity_flags.append("date_inferred_from_inline")
    date_conf = 0.6 if parsed_dt else (0.2 if raw_date else 0.0)
    if raw_date and parsed_dt is None:
        warnings.append("date_unparsed")

    attachments = _extract_attachments(record_text)
    if FORWARD_MARKER_RE.search(record_text):
        warnings.append("contains_forward_chain")

    body_clean, noise_warnings = _clean_body(body_raw)
    warnings.extend(noise_warnings)
    if not body_raw.strip():
        warnings.append("blank_body")

    return MessageRecord(
        message_id=f"msg-{record_index:06d}",
        record_index=record_index,
        source_start_line=start_line,
        source_end_line=end_line,
        raw_record=record_text,
        from_field=_field(raw_from, from_norm, from_conf, from_ambiguous, from_source),
        to_field=_field(raw_to, to_norm, to_conf, to_ambiguous, to_source),
        cc_field=_field(raw_cc, cc_norm, cc_conf, cc_ambiguous, cc_source),
        subject_field=_field(raw_subject, subject_norm, subject_conf, subject_ambiguous, subject_source),
        date_field=_field(raw_date, parsed_dt.isoformat() if parsed_dt else None, date_conf, date_ambiguous, date_source),
        body_raw=body_raw,
        body_clean=body_clean,
        attachments=attachments,
        warnings=warnings,
        errors=[],
        ambiguity_flags=sorted(set(ambiguity_flags)),
        parsed_datetime=parsed_dt,
    )


def build_conversations(messages: Iterable[MessageRecord]) -> list[Conversation]:
    subject_groups: dict[str, list[MessageRecord]] = defaultdict(list)
    for msg in messages:
        subject_groups[msg.subject_field.normalized or "(no subject)"].append(msg)

    conversations: list[Conversation] = []
    conv_index = 1
    for subject_key in sorted(subject_groups.keys()):
        group = sorted(
            subject_groups[subject_key],
            key=lambda m: (
                m.parsed_datetime.isoformat() if m.parsed_datetime else "9999-12-31T23:59:59",
                m.message_id,
            ),
        )
        conv_messages: list[MessageRecord] = []
        curr_bucket: list[MessageRecord] = []

        for msg in group:
            if not curr_bucket:
                curr_bucket.append(msg)
                continue
            previous = curr_bucket[-1]
            overlap = set(previous.to_field.normalized or []) | {previous.from_field.normalized}
            current_people = set(msg.to_field.normalized or []) | {msg.from_field.normalized}
            people_overlap = bool((overlap - {""}) & (current_people - {""}))
            close_in_time = (
                previous.parsed_datetime
                and msg.parsed_datetime
                and abs((msg.parsed_datetime - previous.parsed_datetime).days) <= 14
            )
            if people_overlap or close_in_time:
                curr_bucket.append(msg)
            else:
                conv_messages.extend(curr_bucket)
                curr_bucket = [msg]
        conv_messages.extend(curr_bucket)

        # Conservative baseline: one conversation per subject bucket.
        message_ids = [m.message_id for m in conv_messages]
        dts = sorted([m.parsed_datetime for m in conv_messages if m.parsed_datetime])
        ambiguity = []
        if any(m.parsed_datetime is None for m in conv_messages):
            ambiguity.append("missing_dates_in_group")
        if any(not m.from_field.normalized for m in conv_messages):
            ambiguity.append("missing_sender_in_group")

        conversations.append(
            Conversation(
                conversation_id=f"conv-{conv_index:06d}",
                subject_normalized=subject_key,
                message_ids=message_ids,
                first_at=dts[0].isoformat() if dts else None,
                last_at=dts[-1].isoformat() if dts else None,
                ambiguity_flags=ambiguity,
            )
        )
        conv_index += 1

    conversations.sort(
        key=lambda c: (
            c.last_at or "0000-00-00T00:00:00",
            c.conversation_id,
        ),
        reverse=True,
    )
    return conversations


def build_report(records_seen: int, messages: list[MessageRecord], conversations: list[Conversation]) -> dict:
    conf = Counter()
    ambiguity_count = Counter()
    for msg in messages:
        for field_name in ["from_field", "to_field", "cc_field", "subject_field", "date_field"]:
            field = getattr(msg, field_name)
            band = "low" if field.confidence < 0.5 else ("medium" if field.confidence < 0.8 else "high")
            conf[f"{field_name}:{band}"] += 1
        for flag in msg.ambiguity_flags:
            ambiguity_count[flag] += 1

    parsed_messages = len(messages)
    skipped = max(0, records_seen - parsed_messages)
    return {
        "records_seen": records_seen,
        "messages_parsed": parsed_messages,
        "skipped_unparsed_fragments": skipped,
        "confidence_distribution": dict(conf),
        "ambiguity_counts": dict(ambiguity_count),
        "conversation_count": len(conversations),
    }


def parse_text(raw_text: str) -> ParseResult:
    segmented = segment_records(raw_text)
    messages: list[MessageRecord] = []
    for idx, (start, end, record_text) in enumerate(segmented, start=1):
        try:
            msg = parse_record(record_text, idx, start, end)
            messages.append(msg)
        except (ValueError, IndexError, KeyError, AttributeError, TypeError) as exc:  # pragma: no cover
            messages.append(
                MessageRecord(
                    message_id=f"msg-{idx:06d}",
                    record_index=idx,
                    source_start_line=start,
                    source_end_line=end,
                    raw_record=record_text,
                    body_raw=record_text,
                    body_clean=record_text,
                    warnings=["record_parse_failed"],
                    errors=[str(exc)],
                )
            )

    conversations = build_conversations(messages)
    report = build_report(len(segmented), messages, conversations)
    return ParseResult(messages=messages, conversations=conversations, report=report)


def parse_file(path: str) -> ParseResult:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return parse_text(fh.read())


def write_json(result: ParseResult, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, sort_keys=True)
