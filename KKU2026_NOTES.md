# KKU 2026 manual Swiss draw

Create the KKU event with its 48 countries, open Round 1, then click จับสลากแมนนวล.
Click country names in external draw order. Each selected country displays its position (1, 2, 3…). Click again to remove it and renumber the remaining selections. Adjacent positions form pairs (1–2, 3–4…). Save a partial draft or confirm when all 48 are selected.

The server validates country membership, duplicates, completeness and stale edits. Confirming preserves existing match IDs and refuses to change scored matches or rounds followed by later rounds. Existing draw drafts migrate without deleting match results.

New KkuSwissDraw metadata table is created by the application's existing db.create_all startup. The country roster and flag assets ship with the code. Production event creation happens through the authenticated KKU page; local database files must not be deployed.

Validation: 12 tests in tests/test_kku2026.py; browser checked selection, deselection with renumbering and draft persistence.
