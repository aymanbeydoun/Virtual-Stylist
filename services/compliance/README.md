# BFL Group — Elite Compliance & Audit AI Agent

Validates the authenticity, sourcing legitimacy, and chain of title of goods
purchased through sanitized invoice documentation, protecting BFL Group from
counterfeit goods, unauthorized diversion, and chain-of-title breaks. The
agent gives the Buying Team rigorous, independent verification — its output
is strictly advisory; the purchase decision stays with the buyers.

## What it does

Buyers drag and drop the deal's documents (PDF invoices, chain-of-title
invoices, packing lists, airway bills, Excel extracts, product photos) into
the dashboard, and the agent:

1. **Checks sanitization integrity** — permitted redactions (third-party
   pricing, unrelated customers) vs. strict rejections (vendor identity,
   invoice number/date, SKU/EAN/GTIN, quantities, descriptions, country of
   origin, shipment references, chain-of-title evidence). Redacted dates or
   quantities are flagged as critical.
2. **Runs the step-by-step validation protocol** — invoice verification
   (including font/alignment forensics on scans), vendor due diligence,
   chain-of-title mapping with proof-of-movement and timing plausibility,
   SKU/quantity flow testing (quantity inflation + mid-chain SKU
   introduction), and brand-authorization category coverage.
3. **Assigns a risk rating** — LOW / MEDIUM / HIGH, rendered as a
   **Green / Amber / Red** signal: green = proceed, amber = the team
   discusses collectively and takes a call, red = cannot proceed.
4. **Lists documents requested but not received** from the standard
   requirement list (proof of payment, bill of lading, QC report, …) and
   appends the mandatory Audit & Compliance disclaimer to every report —
   enforced server-side, verbatim.

The model reads PDFs and images natively (high-fidelity OCR — fonts,
misaligned tables, stamps), so scanned invoices and photos work as well as
digital documents. Excel workbooks are extracted to text tables server-side.

## Architecture

```
app/
  agent/
    protocol.py    # system prompt (7-step protocol) + verbatim disclaimer + report JSON schema
    checklist.py   # standard document requirement list
    documents.py   # intake: PDF/image -> native blocks, XLSX/CSV -> extracted text
    gateway.py     # AnthropicAuditGateway (Claude, structured output) + StubAuditGateway
    service.py     # orchestration; attaches signal + disclaimer server-side
  api/routes.py    # POST /api/v1/audits, GET /api/v1/checklist, GET /api/v1/health
  web/index.html   # Red-flag dashboard (drag & drop multi-upload, G/A/R signal)
```

Real audits run on the Claude API (`claude-opus-4-8` by default) with
adaptive thinking, streaming, prompt caching of the static protocol prompt,
and structured outputs so every report parses into the typed schema. The
`stub` backend returns deterministic canned reports for development and CI
and refuses to run in production.

## Run it

```bash
cd services/compliance
uv sync
cp .env.example .env   # set COMPLIANCE_AUDIT_BACKEND=anthropic + API key for real audits
uv run uvicorn app.main:app --reload --port 8100
```

Dashboard: http://localhost:8100 · API docs: http://localhost:8100/api/v1/docs

## Checks

```bash
uv run ruff check .
uv run mypy app
uv run pytest -q
```
