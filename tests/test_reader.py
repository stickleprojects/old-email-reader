from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unittest

from old_email_reader.parser import parse_text
from old_email_reader.reader import build_browse_rows, filter_messages


FIXTURE = Path(__file__).parent / "fixtures" / "mixed_export.txt"


class ReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        text = FIXTURE.read_text(encoding="utf-8")
        self.result = parse_text(text)

    def test_filter_by_date_range(self) -> None:
        filtered = filter_messages(
            self.result.messages,
            date_start=datetime(2003, 11, 27, 0, 0),
            date_end=datetime(2003, 11, 27, 23, 59),
        )
        self.assertTrue(all(m.parsed_datetime is not None for m in filtered))
        self.assertEqual(len(filtered), 1)

    def test_filter_by_from_partial_normalized(self) -> None:
        filtered = filter_messages(self.result.messages, from_contains="alice")
        self.assertGreaterEqual(len(filtered), 2)
        self.assertTrue(all("alice" in (m.from_field.normalized or "") for m in filtered))

    def test_filter_by_to_partial_normalized(self) -> None:
        filtered = filter_messages(self.result.messages, to_contains="bob")
        self.assertGreaterEqual(len(filtered), 3)

    def test_text_search_subject_and_body(self) -> None:
        by_subject = filter_messages(self.result.messages, text_query="project update")
        by_body = filter_messages(self.result.messages, text_query="deterministic grouping")
        self.assertGreaterEqual(len(by_subject), 2)
        self.assertEqual(len(by_body), 1)

    def test_browse_rows_are_deterministic(self) -> None:
        rows = build_browse_rows(self.result)
        self.assertGreaterEqual(len(rows), 1)
        stable = sorted(rows, key=lambda r: ((r["last_at"] or ""), r["conversation_id"]), reverse=True)
        self.assertEqual(rows, stable)


if __name__ == "__main__":
    unittest.main()
