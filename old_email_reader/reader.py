from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import MessageRecord, ParseResult
from .normalizers import contains_text, normalize_identity


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def filter_messages(
    messages: Iterable[MessageRecord],
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    from_contains: str | None = None,
    to_contains: str | None = None,
    text_query: str | None = None,
    include_raw: bool = False,
) -> list[MessageRecord]:
    from_norm = normalize_identity(from_contains or "") if from_contains else ""
    to_norm = normalize_identity(to_contains or "") if to_contains else ""
    query = (text_query or "").strip().lower()

    filtered: list[MessageRecord] = []
    for msg in messages:
        dt = msg.parsed_datetime
        if date_start and (dt is None or dt < date_start):
            continue
        if date_end and (dt is None or dt > date_end):
            continue
        if from_norm and from_norm not in (msg.from_field.normalized or ""):
            continue
        if to_norm:
            recipients = msg.to_field.normalized or []
            if not any(to_norm in rec for rec in recipients):
                continue
        if query:
            content = f"{msg.subject_field.raw}\n{msg.body_clean}"
            if include_raw:
                content += f"\n{msg.body_raw}"
            if query not in content.lower():
                continue
        filtered.append(msg)

    filtered.sort(
        key=lambda m: (
            m.parsed_datetime.isoformat() if m.parsed_datetime else "0000-00-00T00:00:00",
            m.message_id,
        )
    )
    return filtered


def build_browse_rows(
    result: ParseResult,
    date_start: datetime | None = None,
    date_end: datetime | None = None,
    from_contains: str | None = None,
    to_contains: str | None = None,
    text_query: str | None = None,
    include_raw: bool = False,
) -> list[dict]:
    msg_map = {m.message_id: m for m in result.messages}
    selected = {
        m.message_id
        for m in filter_messages(
            result.messages,
            date_start=date_start,
            date_end=date_end,
            from_contains=from_contains,
            to_contains=to_contains,
            text_query=text_query,
            include_raw=include_raw,
        )
    }

    rows: list[dict] = []
    for conv in result.conversations:
        conv_messages = [msg_map[mid] for mid in conv.message_ids if mid in selected]
        if not conv_messages:
            continue
        conv_messages.sort(
            key=lambda m: (
                m.parsed_datetime.isoformat() if m.parsed_datetime else "0000-00-00T00:00:00",
                m.message_id,
            )
        )
        rows.append(
            {
                "conversation_id": conv.conversation_id,
                "subject": conv.subject_normalized,
                "message_count": len(conv_messages),
                "first_at": conv.first_at,
                "last_at": conv.last_at,
                "ambiguity_flags": conv.ambiguity_flags,
                "messages": [
                    {
                        "message_id": m.message_id,
                        "date": m.date_field.normalized,
                        "from": m.from_field.normalized,
                        "to": m.to_field.normalized,
                        "subject": m.subject_field.raw,
                        "preview": (m.body_clean or m.body_raw).strip().replace("\n", " ")[:180],
                        "warnings": m.warnings,
                    }
                    for m in conv_messages
                ],
            }
        )

    rows.sort(
        key=lambda row: (
            row["last_at"] or "0000-00-00T00:00:00",
            row["conversation_id"],
        ),
        reverse=True,
    )
    return rows
