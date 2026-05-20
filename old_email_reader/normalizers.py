from __future__ import annotations

from datetime import datetime
import re

DATE_PATTERNS = ["%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%y %H:%M"]


def normalize_identity(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.lower().startswith("cn="):
        match = re.search(r"CN=([^/]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().lower()
    if "@" in text:
        return text.lower().strip()
    cleaned = re.sub(r"\s+", " ", text)
    cleaned = cleaned.replace("/", " ").strip()
    return cleaned.lower()


def normalize_identities(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = [p.strip() for p in re.split(r",|;", raw) if p.strip()]
    return [normalize_identity(p) for p in parts]


def normalize_subject(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "(no subject)"
    text = re.sub(r"^(\s*(re|fw|fwd)\s*:\s*)+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower() or "(no subject)"


def parse_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def contains_text(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()
