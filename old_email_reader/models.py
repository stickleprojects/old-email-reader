from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class ExtractedField:
    raw: str = ""
    normalized: Any = None
    confidence: float = 0.0
    ambiguous: bool = False
    source: str = "missing"


@dataclass
class MessageRecord:
    message_id: str
    record_index: int
    source_start_line: int
    source_end_line: int
    raw_record: str
    from_field: ExtractedField = field(default_factory=ExtractedField)
    to_field: ExtractedField = field(default_factory=ExtractedField)
    cc_field: ExtractedField = field(default_factory=ExtractedField)
    subject_field: ExtractedField = field(default_factory=ExtractedField)
    date_field: ExtractedField = field(default_factory=ExtractedField)
    body_raw: str = ""
    body_clean: str = ""
    attachments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ambiguity_flags: list[str] = field(default_factory=list)
    parsed_datetime: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["parsed_datetime"] = self.parsed_datetime.isoformat() if self.parsed_datetime else None
        return data


@dataclass
class Conversation:
    conversation_id: str
    subject_normalized: str
    message_ids: list[str]
    first_at: str | None
    last_at: str | None
    ambiguity_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseResult:
    messages: list[MessageRecord]
    conversations: list[Conversation]
    report: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self.messages],
            "conversations": [c.to_dict() for c in self.conversations],
            "report": self.report,
        }
