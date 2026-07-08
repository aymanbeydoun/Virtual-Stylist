from fastapi.testclient import TestClient

from app.agent.protocol import STANDARD_DISCLAIMER
from tests.conftest import INVOICE_CSV, TINY_PDF, TINY_PNG


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "audit_backend": "stub"}


def test_checklist_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/checklist")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 10
    assert all({"name", "why_needed"} <= set(item) for item in items)


def test_dashboard_served_at_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Run Compliance Audit" in response.text


def test_dashboard_fonts_self_hosted(client: TestClient) -> None:
    """The UI's typeface ships with the app — no CDN, works offline."""
    assert 'src: url("/static/fonts/' in client.get("/").text
    response = client.get("/static/fonts/ibm-plex-sans-latin-400.woff2")
    assert response.status_code == 200
    assert response.content.startswith(b"wOF2")


def test_audit_endpoint_end_to_end(client: TestClient) -> None:
    response = client.post(
        "/api/v1/audits",
        files=[
            ("files", ("invoice.pdf", TINY_PDF, "application/pdf")),
            ("files", ("photo.png", TINY_PNG, "image/png")),
            ("files", ("chain.csv", INVOICE_CSV, "text/csv")),
        ],
        data={
            "case_reference": "BFL-2026-0042",
            "vendor_name": "Acme Trading FZE",
            "brand": "ExampleBrand",
            "product_category": "apparel",
            "notes": "second shipment from this vendor",
        },
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["risk_rating"] in {"LOW", "MEDIUM", "HIGH"}
    assert report["signal"] in {"GREEN", "AMBER", "RED"}
    assert report["disclaimer"] == STANDARD_DISCLAIMER
    assert len(report["documents_analyzed"]) == 3
    assert report["case_reference"] == "BFL-2026-0042"
    # The CSV contains "mixed garments" — the stub must escalate.
    assert report["signal"] == "RED"


def test_audit_rejects_unsupported_file(client: TestClient) -> None:
    response = client.post(
        "/api/v1/audits",
        files=[("files", ("contract.docx", b"PK\x03\x04junk", "application/octet-stream"))],
    )
    assert response.status_code == 422
    assert "unsupported file type" in response.json()["detail"]


def test_audit_requires_files(client: TestClient) -> None:
    response = client.post("/api/v1/audits", data={"vendor_name": "Acme"})
    assert response.status_code == 422
