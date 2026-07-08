"""Standard supporting-document requirement list for a parallel-sourcing audit.

Step 7 of the protocol requires every report to list which of these were
requested but not received. The same list is surfaced in the UI so buyers
know what to collect from the vendor up front.
"""
from __future__ import annotations

STANDARD_DOCUMENT_CHECKLIST: list[dict[str, str]] = [
    {
        "name": "Commercial invoice to BFL",
        "why_needed": "Anchors the transaction under review: vendor, SKUs, quantities, value.",
    },
    {
        "name": "Full chain-of-title invoices back to the brand / authorized distributor",
        "why_needed": (
            "Maps every resale link from the brand owner to the final vendor; the "
            "first-chain invoice anchors quantity and SKU flow testing."
        ),
    },
    {
        "name": "Proof of payment (bank transfer / remittance advice)",
        "why_needed": "Confirms the purchases in the chain were genuinely settled.",
    },
    {
        "name": "Bill of lading / airway bill",
        "why_needed": "Independent carrier evidence that goods physically moved between links.",
    },
    {
        "name": "Packing list",
        "why_needed": (
            "Reconciles cartons, units, and SKUs against invoices and transport documents."
        ),
    },
    {
        "name": "Delivery notes / warehouse receiving records",
        "why_needed": "An invoice is not proof of physical receipt; goods-in records are.",
    },
    {
        "name": "Customs declarations / import documentation",
        "why_needed": "Verifies cross-border movement, country of origin, and timing plausibility.",
    },
    {
        "name": "Brand authorization or distributor agreement (exact product category)",
        "why_needed": (
            "Authorization must cover the exact category under review; a retailer is "
            "not automatically an authorized wholesale distributor."
        ),
    },
    {
        "name": "Vendor trade license",
        "why_needed": (
            "Confirms legal existence and that business activity covers trading in goods."
        ),
    },
    {
        "name": "Vendor tax / VAT registration certificate",
        "why_needed": "Cross-checks the tax registration number quoted on the invoice.",
    },
    {
        "name": "QC / inspection report",
        "why_needed": "Independent physical check of product authenticity and condition.",
    },
    {
        "name": "Product photos incl. barcodes (EAN/UPC) and labels",
        "why_needed": "Lets barcodes and labelling be matched against invoiced SKUs.",
    },
]


def checklist_names() -> list[str]:
    return [item["name"] for item in STANDARD_DOCUMENT_CHECKLIST]


def format_checklist_for_prompt() -> str:
    return "\n".join(
        f"{i}. {item['name']} — {item['why_needed']}"
        for i, item in enumerate(STANDARD_DOCUMENT_CHECKLIST, start=1)
    )
