"""Document intake: turn uploaded files into Claude content blocks.

PDFs and images go to the model natively (its vision handles OCR, layout,
stamps, and font/alignment anomalies). Spreadsheets are extracted to text
tables with openpyxl since the API has no native xlsx block; the extraction
note tells the model the values came from a raw workbook.
"""
from __future__ import annotations

import base64
import csv
import io
from dataclasses import dataclass, field
from typing import Any

from openpyxl import load_workbook

from app.schemas.audit import DocumentSummary


class UnsupportedDocumentError(Exception):
    def __init__(self, filename: str, detail: str) -> None:
        self.filename = filename
        self.detail = detail
        super().__init__(f"{filename}: {detail}")


_IMAGE_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

_EXCEL_EXTENSIONS = {"xlsx", "xlsm"}
_TEXT_EXTENSIONS = {"csv", "txt", "tsv"}

_MAX_SHEET_ROWS = 400
_MAX_SHEET_COLS = 40


@dataclass
class DocumentBundle:
    """Content blocks plus the human-readable inventory of what was processed."""

    blocks: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[DocumentSummary] = field(default_factory=list)


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def detect_kind(filename: str, data: bytes) -> str:
    """Classify by magic bytes first, extension second."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    for signature, media_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    ext = _extension(filename)
    if data.startswith(b"PK\x03\x04") and ext in _EXCEL_EXTENSIONS:
        return "excel"
    if ext in _TEXT_EXTENSIONS:
        return "text"
    return "unknown"


def _excel_to_text(filename: str, data: bytes) -> tuple[str, str]:
    """Extract cell values sheet by sheet. Returns (text, note)."""
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many concrete types
        raise UnsupportedDocumentError(
            filename, f"could not be read as an Excel workbook ({exc})"
        ) from exc

    parts: list[str] = []
    truncated = False
    try:
        for sheet in workbook.worksheets:
            rows: list[str] = []
            for r, row in enumerate(sheet.iter_rows(values_only=True)):
                if r >= _MAX_SHEET_ROWS:
                    truncated = True
                    break
                if len(row) > _MAX_SHEET_COLS:
                    truncated = True
                    row = row[:_MAX_SHEET_COLS]
                cells = ["" if cell is None else str(cell) for cell in row]
                if any(cells):
                    rows.append("\t".join(cells))
            parts.append(f"--- Sheet: {sheet.title} ({len(rows)} non-empty rows) ---\n" +
                         ("\n".join(rows) if rows else "(empty)"))
    finally:
        workbook.close()

    note = "Extracted cell values from Excel workbook."
    if truncated:
        note += (
            f" Truncated to {_MAX_SHEET_ROWS} rows / {_MAX_SHEET_COLS} columns per sheet;"
            " request a smaller extract if key data is cut off."
        )
    return "\n\n".join(parts), note


def _csv_to_text(filename: str, data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    if _extension(filename) == "csv":
        # Re-render through the csv parser so quoted fields read cleanly.
        rows = list(csv.reader(io.StringIO(text)))[:_MAX_SHEET_ROWS]
        return "\n".join("\t".join(row) for row in rows)
    return text


def build_document_bundle(files: list[tuple[str, bytes]]) -> DocumentBundle:
    """Convert (filename, bytes) uploads into API content blocks.

    Raises UnsupportedDocumentError for files the agent cannot analyze —
    rejecting loudly beats silently auditing a subset of the evidence.
    """
    bundle = DocumentBundle()
    for index, (filename, data) in enumerate(files, start=1):
        if not data:
            raise UnsupportedDocumentError(filename, "file is empty")
        kind = detect_kind(filename, data)
        label = f"Document {index}: {filename}"

        if kind == "pdf":
            bundle.blocks.append({"type": "text", "text": f"{label} (PDF, shown next)"})
            bundle.blocks.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                }
            )
            bundle.summaries.append(
                DocumentSummary(filename=filename, kind="pdf", size_bytes=len(data))
            )
        elif kind.startswith("image/"):
            bundle.blocks.append({"type": "text", "text": f"{label} (image, shown next)"})
            bundle.blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": kind,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                }
            )
            bundle.summaries.append(
                DocumentSummary(filename=filename, kind="image", size_bytes=len(data))
            )
        elif kind == "excel":
            text, note = _excel_to_text(filename, data)
            bundle.blocks.append({"type": "text", "text": f"{label} ({note})\n\n{text}"})
            bundle.summaries.append(
                DocumentSummary(filename=filename, kind="excel", size_bytes=len(data), note=note)
            )
        elif kind == "text":
            body = _csv_to_text(filename, data)
            bundle.blocks.append({"type": "text", "text": f"{label} (plain text/CSV)\n\n{body}"})
            bundle.summaries.append(
                DocumentSummary(filename=filename, kind="text", size_bytes=len(data))
            )
        else:
            ext = _extension(filename) or "no extension"
            detail = (
                f"unsupported file type ({ext}). Supported: PDF, PNG, JPEG, GIF, WebP, "
                "XLSX/XLSM, CSV, TXT. Legacy .xls files should be re-saved as .xlsx."
            )
            raise UnsupportedDocumentError(filename, detail)
    return bundle
