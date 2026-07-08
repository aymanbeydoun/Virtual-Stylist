# Intelligence E2E Pipeline — Playwright + LLM Assertions

Tests the BFL Compliance Agent end to end — **the interface and the
intelligence** — with no human clicking buttons or reading documents.

## The loop

For each of the **52 pre-configured dummy sanitized invoice cases**:

1. **Trigger** — Playwright uploads the case's documents (PDF invoices,
   Excel/CSV extracts, letters, receipts) through the real front-end.
2. **Execution** — the app's primary AI agent audits them and renders a
   risk rating + reasoning on the dashboard.
3. **Capture** — the script scrapes the rating, rationale, red flags, step
   results and tables **directly from the DOM** (`data-testid` hooks).
4. **AI assertion** — the scraped output plus the case's ground truth go to
   the **Senior Auditor AI** (`claude-opus-4-8`, structured output), which
   grades: defect detection, rating consistency, math reconciliation, and a
   hallucination screen.
5. **Verdict** — a `FAIL` payload (or a deterministic gate failure) fails
   the test, which fails the build. The logical error is written to
   `e2e-artifacts/<fixture>/` (ground truth, scraped output, verdict,
   screenshot) and surfaced as a GitHub annotation for the developers.

Two cheap deterministic gates run before LLM grading: the signal must be in
the fixture's expected set, and the mandatory disclaimer must be rendered.

## The invoice library (`invoice_lab/`)

Seeded, deterministic — the same fixture always produces byte-identical
documents. 10 scenario families × variants = 52 cases:

| Scenario | Seeded defect | Expected signal |
|---|---|---|
| `clean_chain` | none (control — catches false alarms/hallucinations) | GREEN/AMBER |
| `mid_chain_sku_introduction` | SKU billed to BFL absent from first-chain invoice | RED |
| `quantity_inflation` | downstream qty exceeds upstream anchor | RED |
| `masked_anchor_quantity` | anchor quantities redacted → flow test invalidated | RED |
| `redacted_invoice_dates` | chain dates blacked out → timing untestable | RED |
| `generic_description` | "mixed garments" lot breaks SKU traceability | AMBER/RED |
| `implausible_timing` | 3-country resale on the same day | AMBER/RED |
| `category_mismatch_authorization` | watches-only letter, apparel goods | AMBER/RED |
| `retailer_not_distributor` | chain starts at a retail till receipt | AMBER/RED |
| `value_mismatch` | line total ≠ qty × unit price on the BFL invoice | AMBER/RED |

Each fixture carries machine-readable ground truth (entities, per-document
line items, defect details, expected outcome) that the Senior Auditor grades
against.

## Running locally

```bash
# 1. Start the app (real agent for the intelligence run)
cd services/compliance
COMPLIANCE_AUDIT_BACKEND=anthropic COMPLIANCE_ANTHROPIC_API_KEY=sk-... \
  uv run uvicorn app.main:app --port 8100

# 2. Run the pipeline
cd e2e
uv sync
uv run playwright install chromium

# plumbing only (stub backend + fake auditor is fine, no key needed):
E2E_AUDITOR=fake uv run pytest -q -m "not intelligence"

# the full intelligence gate (real backend + real auditor):
ANTHROPIC_API_KEY=sk-... uv run pytest -m intelligence -n 2
```

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:8100` | Where the app is running |
| `E2E_AUDITOR` | auto | `anthropic` \| `fake` (auto: anthropic if key present) |
| `E2E_AUDITOR_MODEL` | `claude-opus-4-8` | Senior Auditor model |
| `ANTHROPIC_API_KEY` | — | Key for the Senior Auditor |
| `E2E_FIXTURE_LIMIT` | `0` (all) | Round-robin subset size across scenarios |
| `E2E_AUDIT_TIMEOUT_S` | `420` | Max wait per audit (real audits take minutes) |
| `E2E_WORKERS` | CI: `2` | xdist workers (browsers + concurrent audits) |
| `E2E_CHROMIUM_PATH` | — | Use a pre-installed Chromium instead of downloading |
| `E2E_ARTIFACTS_DIR` | `e2e-artifacts` | Where per-fixture evidence is written |

## CI (`.github/workflows/intelligence.yml`)

Runs on **every pushed commit** (any branch) plus `workflow_dispatch`:

- **e2e-plumbing** — stub backend + fake auditor: proves the upload → audit
  → scrape → verdict → build-block loop deterministically. No secrets.
- **intelligence-e2e** — the full 52-case library against the real agent,
  graded by the real Senior Auditor. Fails loudly (does not skip) when the
  `ANTHROPIC_API_KEY` secret is missing. Artifacts are uploaded on every
  run; failures also appear as GitHub error annotations per fixture.

Add both jobs as required status checks in branch protection so a FAIL
blocks merges and deployments.

**Cost note:** a full run makes ~104 Opus-class calls (52 audits + 52
gradings, several minutes each). Superseded pushes to the same branch are
auto-cancelled (`concurrency`), and `E2E_FIXTURE_LIMIT` trims the per-commit
subset (round-robin keeps every scenario family covered) if you want to
reserve the full sweep for `workflow_dispatch`/nightly.

## Honest limits

- The Senior Auditor is itself an LLM: it removes *routine* human QA, but a
  human should still review new fixture scenarios and periodically sample
  PASS verdicts. Grading strictness lives in `auditor/grader.py`.
- Expected-signal sets encode the protocol's own escalation rules; if the
  protocol prompt changes materially, review `invoice_lab/scenarios.py`.
