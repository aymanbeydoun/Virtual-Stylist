import pytest

from app.agent.documents import UnsupportedDocumentError, build_document_bundle, detect_kind
from tests.conftest import INVOICE_CSV, TINY_JPEG, TINY_PDF, TINY_PNG, make_xlsx


def test_detect_kind_uses_magic_bytes_over_extension() -> None:
    assert detect_kind("invoice.pdf", TINY_PDF) == "pdf"
    assert detect_kind("misnamed.txt", TINY_PDF) == "pdf"  # content wins
    assert detect_kind("label.png", TINY_PNG) == "image/png"
    assert detect_kind("photo.jpg", TINY_JPEG) == "image/jpeg"
    assert detect_kind("data.csv", INVOICE_CSV) == "text"
    assert detect_kind("book.xlsx", make_xlsx([["a"]])) == "excel"
    assert detect_kind("mystery.bin", b"\x00\x01\x02") == "unknown"


def test_pdf_and_image_become_native_blocks() -> None:
    bundle = build_document_bundle([("invoice.pdf", TINY_PDF), ("label.png", TINY_PNG)])
    types = [block["type"] for block in bundle.blocks]
    # Each file gets a text label followed by its native block.
    assert types == ["text", "document", "text", "image"]
    assert bundle.blocks[1]["source"]["media_type"] == "application/pdf"
    assert bundle.blocks[3]["source"]["media_type"] == "image/png"
    assert [s.kind for s in bundle.summaries] == ["pdf", "image"]


def test_xlsx_is_extracted_to_text() -> None:
    data = make_xlsx(
        [
            ["invoice_number", "sku", "quantity"],
            ["INV-77", "SKU-1", 500],
        ]
    )
    bundle = build_document_bundle([("chain.xlsx", data)])
    assert len(bundle.blocks) == 1
    text = bundle.blocks[0]["text"]
    assert "Sheet: Invoices" in text
    assert "INV-77\tSKU-1\t500" in text
    assert bundle.summaries[0].kind == "excel"
    assert "Extracted cell values" in bundle.summaries[0].note


def test_csv_is_passed_through_as_text() -> None:
    bundle = build_document_bundle([("invoice.csv", INVOICE_CSV)])
    assert "mixed garments" in bundle.blocks[0]["text"]


def test_empty_file_is_rejected() -> None:
    with pytest.raises(UnsupportedDocumentError, match="empty"):
        build_document_bundle([("blank.pdf", b"")])


def test_unsupported_type_is_rejected_loudly() -> None:
    with pytest.raises(UnsupportedDocumentError, match="unsupported file type"):
        build_document_bundle([("contract.docx", b"PK\x03\x04 not a workbook")])
