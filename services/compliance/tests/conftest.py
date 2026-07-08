from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


# --- tiny valid-enough documents for intake tests -------------------------

TINY_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF\n"
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 17 + b"IEND\xaeB`\x82"
)
TINY_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
INVOICE_CSV = (
    b"invoice_number,date,sku,description,quantity\n"
    b"INV-001,2026-05-01,SKU-9,mixed garments,1200\n"
)


def make_xlsx(rows: list[list[str | int]]) -> bytes:
    import io

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Invoices"
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
