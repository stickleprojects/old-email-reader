# Old Lotus Reader: Implementation Plan

## Review Findings

1. **Mixed source formats (high risk)**
   The sample file is not a single consistent email format. It mixes explicit `From/To/Subject/Body` blocks with inline conversational blocks in the same record.

2. **Nested forwarding and repeated chains (high risk)**
   Message bodies include quoted and forwarded chains, sometimes deeply nested, which can create duplicate top-level messages if not handled carefully.

3. **Missing or blank fields (high risk)**
   `Subject` and `Body` can be blank. Date is not always present in the top block and may only appear in embedded message text.

4. **Inconsistent identity formats (medium risk)**
   Sender/recipient values appear in multiple forms:
   - Lotus/Notes style (`CN=.../OU=.../O=...`)
   - Exchange style (`Name/Region/Org`)
   - SMTP addresses (`user@example.com`)

5. **Body noise contamination (medium risk)**
   Signatures, legal disclaimers, antivirus banners, and attachment markers are mixed into body text and should be classified, not treated as clean message text.

6. **Scope validation**
   The product goal in `readme.md` is feasible, but parser complexity should be made explicit because this data is semi-structured.

## Data Analysis Summary

The sample appears to be a Lotus/Notes-exported archive with:

- Top-level separators (asterisk lines)
- Header wrappers that may contain embedded prior messages
- Inline sender/date/To/cc/Subject structures
- Nested forwarded content
- Sparse and inconsistent metadata

This should be handled by a staged parser pipeline, not a single regex pass.

## Implementation Plan

1. **Define canonical data model**
   - `Message`: `id`, `conversation_id`, `from`, `to[]`, `cc[]`, `subject`, `sent_at`, `body_raw`, `body_clean`, `attachments[]`, `source_range`
   - `Conversation`: `id`, `normalized_subject`, `participants[]`, `first_at`, `last_at`, `message_count`
   - Add parse confidence flags for uncertain fields.

2. **Build ingestion and segmentation layer**
   - Load file as raw text.
   - Split into candidate records using delimiter lines.
   - Preserve line offsets for diagnostics and UI traceability.

3. **Build hybrid parser (rule stack)**
   - Rule A: explicit header parser for `From:/To:/Subject:/Body:` format.
   - Rule B: inline message parser for sender/date + `To/cc/Subject` sections.
   - Rule C: forwarded/original chain extractor for nested fragments.
   - Score and choose best parse per fragment.

4. **Normalize identities and dates**
   - Convert CN/OU/O and Exchange-like names into canonical participant keys.
   - Normalize SMTP to lowercase canonical format.
   - Parse `dd/MM/yyyy HH:mm` and mark unknown timezone when missing.
   - Keep raw and normalized values.

5. **Clean and classify body content**
   - Preserve `body_raw` exactly.
   - Produce `body_clean` by isolating signatures/disclaimers/footers.
   - Extract attachment markers (e.g., `winmail.dat`, image/doc references).

6. **Reconstruct threads**
   - Primary grouping: normalized subject after removing repeated `Re:`/`Fw:` prefixes.
   - Secondary grouping: participant overlap + time proximity.
   - Tertiary linking: detect quoted parent blocks in body text.
   - Mark ambiguous links instead of forcing uncertain parent-child relationships.

7. **Implement filtering and browse API**
   - Filters: date range, from, to/cc participant, subject text.
   - Sorting: latest conversation first, message chronological in thread.
   - Return conversation summaries and expandable message trees.

8. **Build UI skeleton**
   - Left pane: conversation list (subject, participants, last activity).
   - Right pane: threaded view with collapsible quoted sections.
   - Filter bar with removable chips for active filters.

9. **Create test fixtures and regression coverage**
   - Cases: blank fields, forwarded chains, multi-recipient blocks, noisy disclaimers, attachment markers, malformed spacing.
   - Snapshot tests for parsed counts and representative thread structures.
   - Regression tests for deduplication and normalization behavior.

10. **Add observability and fallback behavior**

- Emit parse report: records processed, parsed messages, skipped fragments, confidence distribution.
- Keep unparsed fragments as raw artifacts so no data is silently lost.

## Delivery Phases

1. **Phase 1**: Parser MVP + normalized JSON output + tests on sample file.
2. **Phase 2**: Thread reconstruction + filtering API.
3. **Phase 3**: Reader UI with threaded browsing.
4. **Phase 4**: Quality tuning, edge-case hardening, and performance pass.
