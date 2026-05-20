from __future__ import annotations

from pathlib import Path
import unittest

from old_email_reader.parser import parse_text


FIXTURE = Path(__file__).parent / "fixtures" / "mixed_export.txt"


class ParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FIXTURE.read_text(encoding="utf-8")
        self.result = parse_text(self.text)

    def test_segments_and_duplicate_prevention(self) -> None:
        self.assertEqual(self.result.report["records_seen"], 5)
        self.assertEqual(len(self.result.messages), 5)
        ids = [m.message_id for m in self.result.messages]
        self.assertEqual(len(ids), len(set(ids)))

    def test_blank_fields_are_preserved_and_flagged(self) -> None:
        msg = self.result.messages[0]
        self.assertEqual(msg.subject_field.raw, "")
        self.assertIn("blank_subject", msg.warnings)
        self.assertIn("blank_body", msg.warnings)

    def test_forwarded_and_nested_marker_detection(self) -> None:
        msg = self.result.messages[1]
        self.assertIn("contains_forward_chain", msg.warnings)
        self.assertIn("date_inferred_from_inline", msg.ambiguity_flags)

    def test_attachment_marker_extraction(self) -> None:
        msg = self.result.messages[1]
        self.assertEqual(msg.attachments, ["plan.doc"])

    def test_noise_handling_keeps_raw_and_cleans_body(self) -> None:
        msg = self.result.messages[2]
        self.assertIn("Donovan Data Systems Ltd", msg.body_raw)
        self.assertNotIn("Donovan Data Systems Ltd", msg.body_clean)
        self.assertIn("noise_lines_removed", " ".join(msg.warnings))

    def test_date_parsing_edge_cases(self) -> None:
        valid = self.result.messages[1]
        invalid = self.result.messages[3]
        self.assertIsNotNone(valid.parsed_datetime)
        self.assertIsNone(invalid.parsed_datetime)
        self.assertIn("date_unparsed", invalid.warnings)

    def test_conversation_grouping_deterministic(self) -> None:
        convs = self.result.conversations
        stable = sorted(
            convs,
            key=lambda c: ((c.last_at or "0000-00-00T00:00:00"), c.conversation_id),
            reverse=True,
        )
        self.assertEqual(convs, stable)


if __name__ == "__main__":
    unittest.main()
