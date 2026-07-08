"""Self-tests for the dummy invoice library: 50+ cases, deterministic,
structurally valid documents, coherent ground truth."""
from __future__ import annotations

import hashlib
import io

from openpyxl import load_workbook

from invoice_lab.scenarios import build_library

VALID_SIGNALS = {"GREEN", "AMBER", "RED"}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_library_has_fifty_plus_cases() -> None:
    library = build_library()
    assert len(library) >= 50
    assert len({f.scenario for f in library}) == 10


def test_library_is_deterministic() -> None:
    a, b = build_library(), build_library()
    assert [f.fixture_id for f in a] == [f.fixture_id for f in b]
    for fa, fb in zip(a, b, strict=True):
        assert [(d.filename, _digest(d.data)) for d in fa.documents] == [
            (d.filename, _digest(d.data)) for d in fb.documents
        ]


def test_fixture_ids_are_unique() -> None:
    ids = [f.fixture_id for f in build_library()]
    assert len(ids) == len(set(ids))


def test_every_fixture_is_coherent() -> None:
    for fixture in build_library():
        assert fixture.documents, fixture.fixture_id
        assert fixture.allowed_signals and fixture.allowed_signals <= VALID_SIGNALS
        seeded_keys = {d.key for d in fixture.seeded_defects}
        assert set(fixture.required_defect_keys) <= seeded_keys, fixture.fixture_id
        if fixture.scenario == "clean_chain":
            assert not fixture.seeded_defects
        else:
            assert fixture.required_defect_keys, fixture.fixture_id
        for key in ("case_reference", "vendor_name", "brand", "product_category", "notes"):
            assert fixture.case[key], f"{fixture.fixture_id}: empty case field {key}"
        truth = fixture.ground_truth()
        assert truth["expected"]["allowed_signals"]
        assert len(truth["documents"]) == len(fixture.documents)


def test_generated_documents_are_structurally_valid() -> None:
    for fixture in build_library():
        for doc in fixture.documents:
            assert doc.data, f"{fixture.fixture_id}/{doc.filename} is empty"
            if doc.filename.endswith(".pdf"):
                assert doc.data.startswith(b"%PDF-1.4"), doc.filename
                assert b"xref" in doc.data and doc.data.rstrip().endswith(b"%%EOF")
            elif doc.filename.endswith(".xlsx"):
                workbook = load_workbook(io.BytesIO(doc.data), read_only=True)
                assert workbook.sheetnames
                workbook.close()
            elif doc.filename.endswith(".csv"):
                assert b"," in doc.data
            else:
                raise AssertionError(f"unexpected extension: {doc.filename}")


def test_fixture_limit_spreads_across_scenarios() -> None:
    subset = build_library(limit=10)
    assert len(subset) == 10
    assert len({f.scenario for f in subset}) == 10  # one per scenario, round-robin


def test_exactly_two_plumbing_fixtures() -> None:
    plumbing = [f for f in build_library() if f.plumbing]
    assert {f.scenario for f in plumbing} == {"clean_chain", "generic_description"}
