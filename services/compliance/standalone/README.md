# BFL Group — Elite Compliance & Audit AI Agent

Validates the authenticity, sourcing legitimacy, and chain of title of goods
purchased through sanitized invoice documentation — protecting BFL Group from
counterfeit goods, unauthorized diversion, and chain-of-title breaks. Buyers
drag-and-drop the deal's documents; the agent runs the 7-step validation
protocol and answers with a **Green / Amber / Red** signal, every red flag it
found, and the list of standard documents still missing. Its output is
strictly advisory: the purchase decision stays with the Buying Team.

## What it does

1. **Sanitization integrity** — permitted redactions (third-party pricing,
   unrelated customers) vs. strict rejections (vendor identity, invoice
   number/date, SKU/EAN/GTIN, quantities, descriptions, country of origin,
   shipment references, chain-of-title evidence). Redacted dates or
   quantities are critical red flags.
2. **Step-by-step validation** — invoice verification (including
   font/alignment forensics on scans), vendor due diligence, chain-of-title
   mapping with proof-of-movement and timing plausibility, SKU/quantity flow
   testing (quantity inflation + mid-chain SKU introduction), and
   brand-authorization category coverage.
3. **Risk rating** — LOW / MEDIUM / HIGH rendered as Green (proceed), Amber
   (the team discusses collectively and takes a call), Red (cannot proceed).
4. **Step-7 output** — documents requested but not received from the
   standard requirement list, plus the mandatory Audit & Compliance
   disclaimer appended verbatim to every report, server-side.

PDFs and images are read natively by the model (high-fidelity OCR — fonts,
misaligned tables, stamps, photos); Excel workbooks are extracted
server-side. The dashboard ships its own typeface (IBM Plex, self-hosted) and
works offline behind the firewall.

## Quickstart

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8100
```

Dashboard: http://localhost:8100 · API docs: http://localhost:8100/api/v1/docs

Out of the box this runs the **stub** backend (canned reports, no key) so you
can click through the UI. Real audits need the Anthropic API key — next
section.

## Linking your Anthropic API key

Get a key from the [Anthropic Console](https://console.anthropic.com/) →
**API keys**. It is needed in two places:

**1. The running app (real audits)** — set two values in `.env` (or the
host's environment in deployment):

```bash
COMPLIANCE_AUDIT_BACKEND=anthropic
COMPLIANCE_ANTHROPIC_API_KEY=sk-ant-...
```

The service refuses to start in production with the stub backend, so a
misconfigured deployment fails loudly instead of returning canned reports.

**2. GitHub Actions (the intelligence gate)** — repo **Settings → Secrets
and variables → Actions → New repository secret**:

- Name: `ANTHROPIC_API_KEY`
- Value: your key

The `Intelligence` workflow reads this secret for both the live agent and
the Senior Auditor AI. Without it, the intelligence job fails loudly on
purpose (never a silent green build). Nothing else needs linking — no
database, no third-party services; fonts are bundled.

**Recommended:** in branch protection for `main`, mark these status checks
as required so a failed audit-intelligence run blocks merges:
`E2E plumbing (UI loop, stub backend, no tokens)` and
`Intelligence E2E (50+ invoices, AI-graded)`.

## Architecture

```
app/
  agent/
    protocol.py    # system prompt (7-step protocol) + verbatim disclaimer + report schema
    checklist.py   # standard document requirement list
    documents.py   # intake: PDF/image -> native blocks, XLSX/CSV -> extracted text
    gateway.py     # AnthropicAuditGateway (Claude, structured output) + stub for dev/CI
    service.py     # orchestration; attaches signal + disclaimer server-side
  api/routes.py    # POST /api/v1/audits, GET /api/v1/checklist, GET /api/v1/health
  web/             # dashboard (drag & drop multi-upload, G/A/R signal, self-hosted fonts)
e2e/               # Playwright-to-LLM-assertion pipeline (52-case invoice library)
.github/workflows/
  ci.yml           # ruff + mypy strict + unit tests on every push/PR
  intelligence.yml # UI plumbing job + AI-graded intelligence gate on every push
```

Real audits run on `claude-opus-4-8` (configurable) with adaptive thinking,
streaming, prompt caching, and structured outputs so every report parses
into the typed schema.

## Testing

```bash
# unit + protocol tests (no key, no network)
uv run ruff check . && uv run mypy app && uv run pytest -q

# end-to-end intelligence pipeline — see e2e/README.md
cd e2e && uv sync && uv run playwright install chromium
E2E_AUDITOR=fake uv run pytest -q -m "not intelligence"   # plumbing, no key
uv run pytest -m intelligence -n 2                        # full AI-graded gate
```

The e2e pipeline uploads 52 deterministic dummy invoice cases (seeded
defects: mid-chain SKU introduction, quantity inflation, masked anchor
quantities, redacted dates, and more) through the real UI, scrapes the
dashboard, and has a Senior Auditor AI grade the agent's logic — any FAIL
fails the build. Details and cost knobs: [`e2e/README.md`](e2e/README.md).

## Configuration

All settings are `COMPLIANCE_*` environment variables — see
[`.env.example`](.env.example) and `app/config.py` (backend selection,
model, upload limits, CORS).
