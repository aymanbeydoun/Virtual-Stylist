"""The dummy sanitized-invoice library: 50+ deterministic test cases.

Every fixture is generated from a seeded RNG, so the same fixture_id always
produces byte-identical documents. Each fixture carries machine-readable
ground truth (entities, per-document line items, seeded defects, expected
outcome) that the Senior Auditor AI grades the live agent against.
"""
from __future__ import annotations

import io
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from invoice_lab.pdf import text_pdf

Rng = random.Random

# --- entity pools (fictional) ----------------------------------------------

_BRANDS = [
    ("Nordlicht Apparel", "Hamburg, Germany", "Germany"),
    ("Vela Sportiva", "Milan, Italy", "Italy"),
    ("Cascade Outfitters", "Portland, USA", "USA"),
    ("Maison Aurel", "Lyon, France", "France"),
    ("Kestrel & Co", "Manchester, UK", "UK"),
    ("Harbor Line Denim", "Rotterdam, Netherlands", "Netherlands"),
]
_DISTRIBUTORS = [
    ("Meridian Brands Distribution GmbH", "Frankfurt, Germany", "Germany"),
    ("Atlantica Wholesale S.r.l.", "Bologna, Italy", "Italy"),
    ("Crestpoint Distribution LLC", "Newark, USA", "USA"),
    ("Boreal Trade Partners BV", "Utrecht, Netherlands", "Netherlands"),
]
_WHOLESALERS = [
    ("Sable Peak Trading DMCC", "Dubai, UAE", "UAE"),
    ("Oryx Gate General Trading LLC", "Sharjah, UAE", "UAE"),
    ("Lattice Line Commodities FZE", "Ajman, UAE", "UAE"),
]
_VENDORS = [
    ("Al Manara Global Trading FZE", "Jebel Ali Free Zone, Dubai, UAE", "UAE"),
    ("Zephyr Crown Trading LLC", "Deira, Dubai, UAE", "UAE"),
    ("Quartz Bay International FZC", "SAIF Zone, Sharjah, UAE", "UAE"),
    ("Helio Souk Trading Co LLC", "Abu Dhabi, UAE", "UAE"),
]
_GARMENTS = [
    ("Crew-neck T-shirt, organic cotton", "TSH"),
    ("Slim-fit chino trousers", "CHN"),
    ("Hooded fleece sweatshirt", "HDY"),
    ("Denim jacket, mid-wash", "DJK"),
    ("Performance polo shirt", "PLO"),
    ("Quilted puffer vest", "PUF"),
]

BFL_BUYER = "BFL Group (Brands for Less LLC), Dubai, UAE — TRN 100234567890003"


@dataclass(frozen=True)
class LineItem:
    sku: str
    ean: str
    description: str
    qty: int | str  # str when masked, e.g. "[REDACTED]"
    unit_price: float | str
    line_total: float | str

    def facts(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "ean": self.ean,
            "description": self.description,
            "qty": self.qty,
            "unit_price": self.unit_price,
            "line_total": self.line_total,
        }


@dataclass(frozen=True)
class GeneratedDoc:
    filename: str
    data: bytes
    doc_type: str
    synopsis: str
    content_facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SeededDefect:
    key: str
    summary: str
    details: str


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    scenario: str
    title: str
    case: dict[str, str]
    documents: tuple[GeneratedDoc, ...]
    seeded_defects: tuple[SeededDefect, ...]
    required_defect_keys: tuple[str, ...]
    allowed_signals: frozenset[str]
    grading_notes: str
    plumbing: bool = False

    def ground_truth(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "scenario": self.scenario,
            "title": self.title,
            "case_context": self.case,
            "documents": [
                {
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "synopsis": d.synopsis,
                    "content_facts": d.content_facts,
                }
                for d in self.documents
            ],
            "seeded_defects": [
                {"key": d.key, "summary": d.summary, "details": d.details}
                for d in self.seeded_defects
            ],
            "expected": {
                "allowed_signals": sorted(self.allowed_signals),
                "required_defect_keys": list(self.required_defect_keys),
            },
            "grading_notes": self.grading_notes,
        }


# --- document renderers -----------------------------------------------------


def _money(x: float | str) -> str:
    return x if isinstance(x, str) else f"{x:,.2f}"


def _qty(x: int | str) -> str:
    return x if isinstance(x, str) else f"{x:,}"


def _invoice_pdf(
    *,
    title: str,
    invoice_no: str,
    date: str,
    seller: str,
    seller_addr: str,
    seller_trn: str,
    buyer: str,
    items: list[LineItem],
    currency: str,
    grand_total: float | str,
    origin: str,
    shipment_ref: str,
    extra_lines: list[str] | None = None,
) -> bytes:
    lines = [
        title,
        "=" * 78,
        f"Invoice No: {invoice_no:<24} Date: {date}",
        f"Seller: {seller}",
        f"        {seller_addr}   Tax Reg: {seller_trn}",
        f"Buyer:  {buyer}",
        f"Currency: {currency}    Payment terms: 30 days net    Incoterms: FOB",
        f"Country of Origin: {origin}",
        f"Shipment ref: {shipment_ref}",
        "-" * 78,
        f"{'SKU':<13}{'EAN':<15}{'DESCRIPTION':<30}{'QTY':>8}{'UNIT':>10}{'TOTAL':>12}",
        "-" * 78,
    ]
    for it in items:
        lines.append(
            f"{it.sku:<13}{it.ean:<15}{it.description[:29]:<30}"
            f"{_qty(it.qty):>8}{_money(it.unit_price):>10}{_money(it.line_total):>12}"
        )
    lines += ["-" * 78, f"{'GRAND TOTAL':>66}{_money(grand_total):>12}"]
    if extra_lines:
        lines += ["", *extra_lines]
    return text_pdf(lines)


def _packing_csv(items: list[LineItem], shipment_ref: str) -> bytes:
    rows = ["sku,ean,description,cartons,units,shipment_ref"]
    for it in items:
        units = it.qty if isinstance(it.qty, int) else 0
        cartons = max(1, units // 50) if isinstance(it.qty, int) else 0
        rows.append(
            f"{it.sku},{it.ean},{it.description},{cartons},{_qty(it.qty)},{shipment_ref}"
        )
    return ("\n".join(rows) + "\n").encode()


def _chain_xlsx(chain_rows: list[list[Any]]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ChainSummary"
    sheet.append(["link", "seller", "buyer", "invoice_no", "date", "sku", "qty"])
    for row in chain_rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _delivery_note_csv(vendor: str, date: str, items: list[LineItem], awb: str) -> bytes:
    rows = [
        "document,warehouse,received_date,awb,sku,units_received",
    ]
    for it in items:
        rows.append(f"GRN,BFL DIP Warehouse 4,{date},{awb},{it.sku},{_qty(it.qty)}")
    rows.append(f"# Goods received in full from {vendor}")
    return ("\n".join(rows) + "\n").encode()


def _auth_letter_pdf(brand: str, distributor: str, category: str, year: str) -> bytes:
    return text_pdf(
        [
            f"{brand.upper()} — BRAND AUTHORIZATION LETTER",
            "=" * 70,
            "To whom it may concern,",
            "",
            f"{brand} confirms that {distributor} is an authorized",
            f"wholesale distributor of {brand} products for the",
            f"product category: {category.upper()} ONLY.",
            "",
            f"This authorization covers onward wholesale resale of {category}",
            f"and is valid for the calendar year {year}.",
            "",
            "Brand Protection Office",
            f"{brand}",
        ]
    )


# --- chain assembly ---------------------------------------------------------


@dataclass
class Chain:
    brand: tuple[str, str, str]
    distributor: tuple[str, str, str]
    wholesaler: tuple[str, str, str]
    vendor: tuple[str, str, str]
    skus: list[tuple[str, str, str]]  # (sku, ean, description)
    d1: str
    d2: str
    d3: str
    currency: str = "USD"


def _mk_skus(rng: Rng, brand_name: str, n: int) -> list[tuple[str, str, str]]:
    prefix = "".join(w[0] for w in brand_name.split()[:2]).upper()
    skus = []
    for _ in range(n):
        desc, code = rng.choice(_GARMENTS)
        num = rng.randint(1000, 9899)
        skus.append((f"{prefix}-{code}-{num}", f"40{rng.randint(10**10, 10**11 - 1)}", desc))
    return skus


def _dates(rng: Rng, *, same_day: bool = False) -> tuple[str, str, str]:
    day = rng.randint(3, 14)
    month = rng.choice([2, 3, 4])
    d1 = f"2026-{month:02d}-{day:02d}"
    if same_day:
        return d1, d1, d1
    d2 = f"2026-{month:02d}-{day + rng.randint(6, 9):02d}"
    d3 = f"2026-{month + 1:02d}-{rng.randint(2, 12):02d}"
    return d1, d2, d3


def _mk_chain(rng: Rng, *, n_skus: int = 3, same_day: bool = False) -> Chain:
    brand = rng.choice(_BRANDS)
    d1, d2, d3 = _dates(rng, same_day=same_day)
    return Chain(
        brand=brand,
        distributor=rng.choice(_DISTRIBUTORS),
        wholesaler=rng.choice(_WHOLESALERS),
        vendor=rng.choice(_VENDORS),
        skus=_mk_skus(rng, brand[0], n_skus),
        d1=d1,
        d2=d2,
        d3=d3,
    )


def _items(
    skus: list[tuple[str, str, str]], qtys: list[int], units: list[float]
) -> list[LineItem]:
    out = []
    for (sku, ean, desc), qty, unit in zip(skus, qtys, units, strict=True):
        out.append(LineItem(sku, ean, desc, qty, unit, round(qty * unit, 2)))
    return out


def _grand(items: list[LineItem]) -> float:
    return round(sum(it.line_total for it in items if isinstance(it.line_total, float)), 2)


def _chain_invoices(
    chain: Chain,
    rng: Rng,
    items1: list[LineItem],
    items2: list[LineItem],
    items3: list[LineItem],
    *,
    date1: str | None = None,
    date2: str | None = None,
    grand3: float | str | None = None,
) -> list[GeneratedDoc]:
    """The three invoice PDFs: brand->distributor, distributor->wholesaler/vendor,
    vendor->BFL. Callers pass pre-built (possibly defective) line items."""
    inv1_no = f"BR-{rng.randint(10000, 99999)}"
    inv2_no = f"DS-{rng.randint(10000, 99999)}"
    inv3_no = f"VN-{rng.randint(10000, 99999)}"
    awb = f"AWB 176-{rng.randint(1000000, 9999999)}"

    def doc(
        filename: str,
        title: str,
        no: str,
        date: str,
        seller: tuple[str, str, str],
        buyer: str,
        items: list[LineItem],
        origin: str,
        ref: str,
        grand: float | str | None = None,
    ) -> GeneratedDoc:
        total = _grand(items) if grand is None else grand
        return GeneratedDoc(
            filename=filename,
            data=_invoice_pdf(
                title=title,
                invoice_no=no,
                date=date,
                seller=seller[0],
                seller_addr=seller[1],
                seller_trn=f"TRN {rng.randint(10**11, 10**12 - 1)}",
                buyer=buyer,
                items=items,
                currency=chain.currency,
                grand_total=total,
                origin=origin,
                shipment_ref=ref,
            ),
            doc_type="invoice",
            synopsis=f"{title}: {seller[0]} -> {buyer.split(',')[0]} ({no}, {date})",
            content_facts={
                "invoice_no": no,
                "date": date,
                "seller": seller[0],
                "buyer": buyer,
                "currency": chain.currency,
                "line_items": [it.facts() for it in items],
                "grand_total": total,
                "origin": origin,
                "shipment_ref": ref,
            },
        )

    return [
        doc(
            "01_first_chain_invoice.pdf",
            "COMMERCIAL INVOICE (FIRST CHAIN)",
            inv1_no,
            date1 or chain.d1,
            chain.brand,
            f"{chain.distributor[0]}, {chain.distributor[1]}",
            items1,
            chain.brand[2],
            f"Truck CMR-{rng.randint(100000, 999999)}",
        ),
        doc(
            "02_mid_chain_invoice.pdf",
            "COMMERCIAL INVOICE (MID CHAIN)",
            inv2_no,
            date2 or chain.d2,
            chain.distributor,
            f"{chain.vendor[0]}, {chain.vendor[1]}",
            items2,
            chain.brand[2],
            awb,
        ),
        doc(
            "03_bfl_invoice.pdf",
            "COMMERCIAL INVOICE (TO BFL)",
            inv3_no,
            chain.d3,
            chain.vendor,
            BFL_BUYER,
            items3,
            chain.brand[2],
            awb,
            grand=grand3,
        ),
    ]


def _case(chain: Chain, fixture_id: str, category: str = "apparel") -> dict[str, str]:
    return {
        "case_reference": fixture_id.upper(),
        "vendor_name": chain.vendor[0],
        "brand": chain.brand[0],
        "product_category": category,
        "notes": "Routine parallel-sourcing deal; standard compliance review requested.",
    }


# --- scenario builders ------------------------------------------------------


def build_clean(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng)
    q1 = [rng.randrange(900, 1500, 50) for _ in chain.skus]
    q2 = [q - rng.randrange(0, 100, 50) for q in q1]
    q3 = [q - rng.randrange(0, 100, 50) for q in q2]
    u1 = [round(rng.uniform(3.5, 9.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, q2, [round(u * 1.18, 2) for u in u1])
    items3 = _items(chain.skus, q3, [round(u * 1.40, 2) for u in u1])
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    awb = docs[2].content_facts["shipment_ref"]
    docs.append(
        GeneratedDoc(
            "04_packing_list.csv",
            _packing_csv(items3, awb),
            "packing_list",
            "Packing list for the BFL shipment (matches BFL invoice items).",
            {"line_items": [it.facts() for it in items3]},
        )
    )
    docs.append(
        GeneratedDoc(
            "05_goods_received_note.csv",
            _delivery_note_csv(chain.vendor[0], chain.d3, items3, awb),
            "warehouse_receiving_record",
            "BFL warehouse goods-received note confirming physical receipt.",
            {},
        )
    )
    docs.append(
        GeneratedDoc(
            "06_brand_authorization.pdf",
            _auth_letter_pdf(chain.brand[0], chain.distributor[0], "apparel", "2026"),
            "brand_authorization",
            f"Brand letter authorizing {chain.distributor[0]} for APPAREL wholesale.",
            {"authorized_category": "apparel", "authorized_entity": chain.distributor[0]},
        )
    )
    docs.append(
        GeneratedDoc(
            "07_chain_summary.xlsx",
            _chain_xlsx(
                [
                    [1, chain.brand[0], chain.distributor[0], "see inv 01", chain.d1, s[0], q]
                    for s, q in zip(chain.skus, q1, strict=True)
                ]
                + [
                    [2, chain.distributor[0], chain.vendor[0], "see inv 02", chain.d2, s[0], q]
                    for s, q in zip(chain.skus, q2, strict=True)
                ]
                + [
                    [3, chain.vendor[0], "BFL Group", "see inv 03", chain.d3, s[0], q]
                    for s, q in zip(chain.skus, q3, strict=True)
                ]
            ),
            "chain_summary",
            "Vendor-prepared Excel summary of the full chain (consistent).",
            {},
        )
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="clean_chain",
        title="Fully consistent chain with movement evidence and apparel authorization",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(),
        required_defect_keys=(),
        allowed_signals=frozenset({"GREEN", "AMBER"}),
        grading_notes=(
            "No defects were seeded. Quantities only ever decrease downstream, every "
            "BFL SKU is anchored in the first-chain invoice, dates are sequential and "
            "plausible, movement evidence and an apparel authorization letter are "
            "included. Some standard documents (proof of payment, customs entries, QC "
            "report) were intentionally not provided, so a cautious AMBER with document "
            "requests is acceptable; GREEN is acceptable too. RED would be wrong. "
            "Fabricated defects must be treated as hallucinations."
        ),
        plumbing=variant == 0,
    )


def build_mid_chain_sku(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=3)
    ghost_sku = _mk_skus(rng, chain.brand[0], 1)[0]
    q1 = [rng.randrange(800, 1400, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    ghost_qty = rng.randrange(400, 900, 50)
    items2 = _items(
        [*chain.skus, ghost_sku],
        [*(q - 50 for q in q1), ghost_qty],
        [*(round(u * 1.2, 2) for u in u1), round(rng.uniform(5.0, 9.0), 2)],
    )
    items3 = _items(
        [*chain.skus, ghost_sku],
        [*(q - 100 for q in q1), ghost_qty],
        [*(round(u * 1.45, 2) for u in u1), round(rng.uniform(7.0, 12.0), 2)],
    )
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    awb = docs[2].content_facts["shipment_ref"]
    docs.append(
        GeneratedDoc(
            "04_packing_list.csv",
            _packing_csv(items3, awb),
            "packing_list",
            "Packing list for the BFL shipment.",
            {"line_items": [it.facts() for it in items3]},
        )
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="mid_chain_sku_introduction",
        title="SKU introduced mid-chain, absent from the first-chain invoice",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="mid_chain_sku_introduction",
                summary="A SKU billed to BFL does not exist in the first-chain invoice.",
                details=(
                    f"SKU {ghost_sku[0]} (EAN {ghost_sku[1]}, {ghost_sku[2]}, qty "
                    f"{ghost_qty}) first appears on the mid-chain invoice and is billed "
                    "to BFL, but is absent from the brand's first-chain invoice — "
                    "failing the mid-chain SKU introduction test (protocol Step 4 "
                    "Test B)."
                ),
            ),
        ),
        required_defect_keys=("mid_chain_sku_introduction",),
        allowed_signals=frozenset({"RED"}),
        grading_notes=(
            "The agent must identify that the introduced SKU is not anchored in the "
            "first-chain invoice and escalate to HIGH risk. Naming the exact SKU code "
            "is strong evidence of detection; clearly describing an unanchored/"
            "mid-chain-introduced SKU also counts."
        ),
    )


def build_quantity_inflation(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=3)
    q1 = [rng.randrange(400, 900, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    inflated_idx = rng.randrange(len(chain.skus))
    q3 = list(q1)
    q3[inflated_idx] = q1[inflated_idx] + rng.randrange(200, 500, 50)
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, q3, [round(u * 1.2, 2) for u in u1])
    items3 = _items(chain.skus, q3, [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    docs.append(
        GeneratedDoc(
            "04_chain_summary.xlsx",
            _chain_xlsx(
                [
                    [1, chain.brand[0], chain.distributor[0], "see inv 01", chain.d1, s[0], q]
                    for s, q in zip(chain.skus, q1, strict=True)
                ]
                + [
                    [3, chain.vendor[0], "BFL Group", "see inv 03", chain.d3, s[0], q]
                    for s, q in zip(chain.skus, q3, strict=True)
                ]
            ),
            "chain_summary",
            "Vendor-prepared Excel chain summary (contains the inflated quantity).",
            {},
        )
    )
    sku = chain.skus[inflated_idx][0]
    return Fixture(
        fixture_id=fixture_id,
        scenario="quantity_inflation",
        title="Downstream quantity exceeds the upstream procured quantity",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="quantity_inflation",
                summary="Quantity billed to BFL exceeds the first-chain procured quantity.",
                details=(
                    f"SKU {sku}: first-chain invoice shows {q1[inflated_idx]} units, but "
                    f"{q3[inflated_idx]} units flow downstream to BFL "
                    f"({q3[inflated_idx] - q1[inflated_idx]} units unaccounted for) — "
                    "failing the quantity inflation test (protocol Step 4 Test A)."
                ),
            ),
        ),
        required_defect_keys=("quantity_inflation",),
        allowed_signals=frozenset({"RED"}),
        grading_notes=(
            "The agent must catch that downstream quantity exceeds the upstream anchor "
            "for the affected SKU and escalate to HIGH. Citing the correct unit counts "
            "is strong evidence; the arithmetic it quotes must match the documents."
        ),
    )


def build_masked_anchor_qty(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2)
    q2 = [rng.randrange(500, 1000, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    masked1 = [
        LineItem(s[0], s[1], s[2], "[REDACTED]", u, "[REDACTED]")
        for s, u in zip(chain.skus, u1, strict=True)
    ]
    items2 = _items(chain.skus, q2, [round(u * 1.2, 2) for u in u1])
    items3 = _items(chain.skus, q2, [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(chain, rng, masked1, items2, items3, grand3=None)
    # first invoice grand total is also masked
    docs[0] = GeneratedDoc(
        docs[0].filename,
        _invoice_pdf(
            title="COMMERCIAL INVOICE (FIRST CHAIN)",
            invoice_no=docs[0].content_facts["invoice_no"],
            date=chain.d1,
            seller=chain.brand[0],
            seller_addr=chain.brand[1],
            seller_trn="TRN [REDACTED]",
            buyer=f"{chain.distributor[0]}, {chain.distributor[1]}",
            items=masked1,
            currency=chain.currency,
            grand_total="[REDACTED]",
            origin=chain.brand[2],
            shipment_ref="[REDACTED]",
        ),
        "invoice",
        "First-chain invoice with ALL quantities, totals and shipment refs redacted.",
        {
            "invoice_no": docs[0].content_facts["invoice_no"],
            "date": chain.d1,
            "seller": chain.brand[0],
            "line_items": [it.facts() for it in masked1],
            "grand_total": "[REDACTED]",
            "note": "anchor quantities masked by the vendor's sanitization",
        },
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="masked_anchor_quantity",
        title="Anchor quantities redacted on the first-chain invoice",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="masked_anchor_quantity",
                summary="First-chain quantities are redacted, invalidating flow testing.",
                details=(
                    "Every quantity, the grand total and the shipment reference on the "
                    "first-chain invoice are masked as [REDACTED]. Quantities and "
                    "shipment references are on the strict-rejection list — this is a "
                    "critical sanitization breach, and the entire downstream quantity "
                    "flow test is invalidated because the anchor is unknown."
                ),
            ),
        ),
        required_defect_keys=("masked_anchor_quantity",),
        allowed_signals=frozenset({"RED"}),
        grading_notes=(
            "The agent must (a) flag the redacted quantities/shipment reference as a "
            "critical sanitization violation and (b) state that quantity flow testing "
            "is not possible without the anchor. Claiming to have reconciled "
            "quantities against the masked anchor is a hallucination."
        ),
    )


def build_redacted_dates(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2)
    q1 = [rng.randrange(600, 1100, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.2, 2) for u in u1])
    items3 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(
        chain, rng, items1, items2, items3, date1="[REDACTED]", date2="[REDACTED]"
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="redacted_invoice_dates",
        title="Chain invoice dates blacked out",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="redacted_invoice_dates",
                summary="Upstream invoice dates are redacted, blocking timing tests.",
                details=(
                    "The first-chain and mid-chain invoices show Date: [REDACTED]. "
                    "Invoice dates are on the strict-rejection list; without them the "
                    "timing/sequence plausibility of the chain cannot be tested. "
                    "Critical red flag per the sanitization rules."
                ),
            ),
        ),
        required_defect_keys=("redacted_invoice_dates",),
        allowed_signals=frozenset({"RED"}),
        grading_notes=(
            "The agent must flag the redacted dates as a strict-rejection breach and "
            "mark timing plausibility as untestable. Inventing dates or claiming the "
            "cadence was verified is a hallucination."
        ),
    )


def build_generic_description(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2)
    q1 = [rng.randrange(700, 1200, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    lot_qty = sum(q1) - 100
    lot_value = round(lot_qty * rng.uniform(5.0, 7.0), 2)
    items2 = [LineItem("-", "-", "MIXED GARMENTS, ASSORTED (1 LOT)", lot_qty, "-", lot_value)]
    items3 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    awb = docs[2].content_facts["shipment_ref"]
    packing_items = [
        LineItem("-", "-", "mixed garments assorted", lot_qty, "-", "-"),
    ]
    docs.append(
        GeneratedDoc(
            "04_packing_list.csv",
            _packing_csv(packing_items, awb),
            "packing_list",
            "Packing list describing the goods only as 'mixed garments assorted'.",
            {"line_items": [it.facts() for it in packing_items]},
        )
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="generic_description",
        title="Mid-chain documents use generic 'mixed garments' descriptions",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="generic_untraceable_description",
                summary="Generic 'mixed garments' descriptions break SKU traceability.",
                details=(
                    "The mid-chain invoice and packing list describe the goods only as "
                    f"'MIXED GARMENTS, ASSORTED (1 LOT)' ({lot_qty} units) with no SKU, "
                    "EAN or style data, so the SKUs billed to BFL cannot be traced "
                    "through that link (protocol Step 4)."
                ),
            ),
        ),
        required_defect_keys=("generic_untraceable_description",),
        allowed_signals=frozenset({"AMBER", "RED"}),
        grading_notes=(
            "The agent must flag the generic description as breaking SKU-level "
            "traceability across the mid-chain link. RED or AMBER are both acceptable "
            "ratings; GREEN is a miss."
        ),
        plumbing=variant == 0,
    )


def build_implausible_timing(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2, same_day=True)
    q1 = [rng.randrange(600, 1100, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.2, 2) for u in u1])
    items3 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    return Fixture(
        fixture_id=fixture_id,
        scenario="implausible_timing",
        title="Goods resold across three countries on the same day",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="implausible_timing",
                summary="Same-day resale across countries is not commercially realistic.",
                details=(
                    f"All three invoices are dated {chain.d1}: {chain.brand[2]} -> "
                    f"{chain.distributor[2]} -> UAE -> BFL on a single day, leaving no "
                    "time for customs or physical shipment between links (protocol "
                    "Step 3 timing plausibility)."
                ),
            ),
        ),
        required_defect_keys=("implausible_timing",),
        allowed_signals=frozenset({"AMBER", "RED"}),
        grading_notes=(
            "The agent must notice that every chain link is dated the same day and "
            "call the resale cadence implausible given shipping/customs lead times."
        ),
    )


def build_category_mismatch(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2)
    q1 = [rng.randrange(600, 1100, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.2, 2) for u in u1])
    items3 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.45, 2) for u in u1])
    docs = _chain_invoices(chain, rng, items1, items2, items3)
    docs.append(
        GeneratedDoc(
            "04_brand_authorization.pdf",
            _auth_letter_pdf(chain.brand[0], chain.distributor[0], "watches", "2026"),
            "brand_authorization",
            f"Brand letter authorizing {chain.distributor[0]} for WATCHES only.",
            {"authorized_category": "watches", "authorized_entity": chain.distributor[0]},
        )
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="category_mismatch_authorization",
        title="Distributor authorization covers watches; the goods are apparel",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="authorization_category_mismatch",
                summary="The distributor authorization does not cover the goods' category.",
                details=(
                    f"The authorization letter limits {chain.distributor[0]} to the "
                    "WATCHES category only, while every invoiced item is apparel "
                    "(garments). Authorization for one category does not extend to "
                    "another (protocol Step 5)."
                ),
            ),
        ),
        required_defect_keys=("authorization_category_mismatch",),
        allowed_signals=frozenset({"AMBER", "RED"}),
        grading_notes=(
            "The agent must read the authorization letter's category restriction and "
            "flag that it does not cover apparel. Treating the letter as valid "
            "category coverage is a miss."
        ),
    )


def build_retailer_source(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=2)
    q = [rng.randrange(300, 600, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(6.0, 12.0), 2) for _ in chain.skus]
    receipt_items = _items(chain.skus, q, u1)
    items2 = _items(chain.skus, q, [round(u * 1.15, 2) for u in u1])
    items3 = _items(chain.skus, q, [round(u * 1.35, 2) for u in u1])
    retail_store = f"{chain.brand[0]} Outlet Store #{rng.randint(3, 44)}"
    receipt = GeneratedDoc(
        "01_retail_receipt.pdf",
        text_pdf(
            [
                f"{retail_store.upper()} — RETAIL TILL RECEIPT",
                "=" * 70,
                f"Date: {chain.d1}   Register 04   Cashier 112",
                f"Customer: {chain.wholesaler[0]} (walk-in bulk purchase)",
                "-" * 70,
            ]
            + [
                f"{it.sku:<14}{it.description[:30]:<32}"
                f"{_qty(it.qty):>6} x {_money(it.unit_price):>8}"
                for it in receipt_items
            ]
            + [
                "-" * 70,
                f"TOTAL PAID (CARD): {chain.currency} {_money(_grand(receipt_items))}",
                "Thank you for shopping with us. No commercial resale warranty given.",
            ]
        ),
        "retail_receipt",
        f"Retail till receipt: {retail_store} bulk sale to {chain.wholesaler[0]}.",
        {
            "seller": retail_store,
            "buyer": chain.wholesaler[0],
            "date": chain.d1,
            "line_items": [it.facts() for it in receipt_items],
            "grand_total": _grand(receipt_items),
        },
    )
    docs = _chain_invoices(chain, rng, receipt_items, items2, items3)
    docs[0] = receipt  # the "first chain" evidence is only a retail receipt
    return Fixture(
        fixture_id=fixture_id,
        scenario="retailer_not_distributor",
        title="Chain originates at a retail till receipt, not an authorized distributor",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="retailer_not_authorized_distributor",
                summary="The source is a retail store purchase, not authorized wholesale.",
                details=(
                    f"The earliest chain document is a retail till receipt from "
                    f"{retail_store} for a walk-in bulk purchase by {chain.wholesaler[0]}. "
                    "A genuine retailer is not automatically an authorized wholesale "
                    "distributor; onward wholesale resale needs explicit permission "
                    "(protocol Step 5), and no brand/distributor invoice anchors the "
                    "chain."
                ),
            ),
        ),
        required_defect_keys=("retailer_not_authorized_distributor",),
        allowed_signals=frozenset({"AMBER", "RED"}),
        grading_notes=(
            "The agent must recognize the retail receipt origin as an unauthorized "
            "wholesale source / diversion indicator rather than a valid first-chain "
            "anchor."
        ),
    )


def build_value_mismatch(rng: Rng, fixture_id: str, variant: int) -> Fixture:
    chain = _mk_chain(rng, n_skus=3)
    q1 = [rng.randrange(600, 1100, 50) for _ in chain.skus]
    u1 = [round(rng.uniform(4.0, 8.0), 2) for _ in chain.skus]
    items1 = _items(chain.skus, q1, u1)
    items2 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.2, 2) for u in u1])
    good3 = _items(chain.skus, [q - 50 for q in q1], [round(u * 1.45, 2) for u in u1])
    bad_idx = rng.randrange(len(good3))
    overstated = round(float(good3[bad_idx].line_total) + rng.randrange(1200, 4200, 300), 2)
    bad_item = LineItem(
        good3[bad_idx].sku,
        good3[bad_idx].ean,
        good3[bad_idx].description,
        good3[bad_idx].qty,
        good3[bad_idx].unit_price,
        overstated,
    )
    items3 = [bad_item if i == bad_idx else it for i, it in enumerate(good3)]
    stated_grand = round(
        sum(float(it.line_total) for it in items3), 2
    )  # grand total matches the WRONG line, hiding the error one level up
    docs = _chain_invoices(chain, rng, items1, items2, items3, grand3=stated_grand)
    docs.append(
        GeneratedDoc(
            "04_chain_summary.xlsx",
            _chain_xlsx(
                [
                    [3, chain.vendor[0], "BFL Group", "see inv 03", chain.d3, it.sku, int(it.qty)]
                    for it in items3
                    if isinstance(it.qty, int)
                ]
            ),
            "chain_summary",
            "Vendor Excel summary of the BFL shipment.",
            {},
        )
    )
    correct_total = round(
        float(bad_item.qty) * float(bad_item.unit_price), 2
    )
    return Fixture(
        fixture_id=fixture_id,
        scenario="value_mismatch",
        title="Line total on the BFL invoice does not equal qty x unit price",
        case=_case(chain, fixture_id),
        documents=tuple(docs),
        seeded_defects=(
            SeededDefect(
                key="line_total_math_error",
                summary="A BFL invoice line total contradicts its own qty x unit price.",
                details=(
                    f"SKU {bad_item.sku}: {bad_item.qty} units x "
                    f"{_money(bad_item.unit_price)} = {_money(correct_total)}, but the "
                    f"invoice states {_money(overstated)} "
                    f"({_money(round(overstated - correct_total, 2))} overstated); the "
                    "grand total carries the inflated figure. Basic value "
                    "reconciliation (protocol Steps 1 and 4) fails."
                ),
            ),
        ),
        required_defect_keys=("line_total_math_error",),
        allowed_signals=frozenset({"AMBER", "RED"}),
        grading_notes=(
            "The agent must do the line-level arithmetic and catch the overstated "
            "line total. Any arithmetic the agent itself quotes must be correct — "
            "grade its math against the document facts."
        ),
    )


_BUILDERS: list[tuple[str, int, Callable[[Rng, str, int], Fixture]]] = [
    ("clean_chain", 6, build_clean),
    ("mid_chain_sku_introduction", 6, build_mid_chain_sku),
    ("quantity_inflation", 6, build_quantity_inflation),
    ("masked_anchor_quantity", 5, build_masked_anchor_qty),
    ("redacted_invoice_dates", 5, build_redacted_dates),
    ("generic_description", 5, build_generic_description),
    ("implausible_timing", 5, build_implausible_timing),
    ("category_mismatch_authorization", 5, build_category_mismatch),
    ("retailer_not_distributor", 4, build_retailer_source),
    ("value_mismatch", 5, build_value_mismatch),
]


def build_library(limit: int | None = None) -> list[Fixture]:
    """The full deterministic fixture library (52 cases by default)."""
    fixtures: list[Fixture] = []
    for scenario, variants, builder in _BUILDERS:
        for i in range(variants):
            rng = random.Random(f"bfl-e2e::{scenario}::{i}")
            fixtures.append(builder(rng, f"{scenario}-{i:02d}", i))
    if limit is not None and limit > 0:
        # Spread the cut across scenarios rather than truncating whole classes.
        by_scenario: dict[str, list[Fixture]] = {}
        for f in fixtures:
            by_scenario.setdefault(f.scenario, []).append(f)
        picked: list[Fixture] = []
        round_i = 0
        while len(picked) < limit and any(by_scenario.values()):
            for scenario, _, _ in _BUILDERS:
                bucket = by_scenario.get(scenario, [])
                if round_i < len(bucket) and len(picked) < limit:
                    picked.append(bucket[round_i])
            round_i += 1
        return picked
    return fixtures
