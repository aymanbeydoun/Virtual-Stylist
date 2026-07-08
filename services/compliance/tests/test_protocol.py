"""The protocol module is the contract: disclaimer verbatim, prompt invariants,
and a structured-output schema that is actually strict."""
from typing import Any

from app.agent.checklist import STANDARD_DOCUMENT_CHECKLIST, checklist_names
from app.agent.protocol import REPORT_JSON_SCHEMA, STANDARD_DISCLAIMER, SYSTEM_PROMPT

# Duplicated verbatim from the compliance specification on purpose: if anyone
# edits the disclaimer in code, this test must fail.
EXPECTED_DISCLAIMER = (
    "Audit & Compliance has performed the above procedures based on standard risk and "
    "control considerations. This review does not constitute approval or endorsement and "
    "should not be considered exhaustive, nor a substitute for legal or commercial review. "
    "It is expected that the responsible stakeholders exercise their professional judgment "
    "and perform any additional checks deemed necessary to mitigate risks and validate "
    "(qualitative and quantitative) authenticity of the products under consideration. The "
    "input provided is strictly advisory in nature. In the absence of complete supporting "
    "documentation, the authenticity and source of the inventory cannot be independently "
    "validated. Consequently, any decision to proceed with the purchase remains a commercial "
    "decision for the Buying team, made after considering the associated business, brand, "
    "and compliance risks disclosed in this assessment."
)


def test_disclaimer_is_verbatim() -> None:
    assert STANDARD_DISCLAIMER == EXPECTED_DISCLAIMER


def test_system_prompt_encodes_core_directives() -> None:
    # Sanitization: the strictly-rejected redactions must all be named.
    for term in [
        "vendor identity",
        "invoice number/date",
        "barcode/EAN/GTIN",
        "quantity",
        "country of origin",
        "shipment references",
        "chain-of-title evidence",
    ]:
        assert term in SYSTEM_PROMPT, f"missing strict-rejection term: {term}"

    # The non-negotiable investigation rules.
    assert "never treat a brand relationship as verified using contact details" in SYSTEM_PROMPT
    assert "an invoice is not proof of physical receipt" in SYSTEM_PROMPT.lower()
    assert "mixed garments" in SYSTEM_PROMPT
    assert "Quantity Inflation" in SYSTEM_PROMPT
    assert "Mid-Chain SKU Introduction" in SYSTEM_PROMPT
    # The model must not emit the disclaimer itself; the server appends it.
    assert "appends it verbatim" in SYSTEM_PROMPT

    # The full standard checklist is in the prompt.
    for name in checklist_names():
        assert name in SYSTEM_PROMPT


def test_checklist_covers_spec_examples() -> None:
    names = " | ".join(checklist_names()).lower()
    for required in ["proof of payment", "bill of lading", "qc / inspection report"]:
        assert required in names
    assert all(item["why_needed"] for item in STANDARD_DOCUMENT_CHECKLIST)


def _assert_strict(schema: dict[str, Any], path: str = "$") -> None:
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, f"{path}: open object"
        props = schema.get("properties", {})
        assert set(schema.get("required", [])) == set(props), f"{path}: required != properties"
        for key, sub in props.items():
            _assert_strict(sub, f"{path}.{key}")
    if schema.get("type") == "array":
        _assert_strict(schema["items"], f"{path}[]")


def test_report_schema_is_strict_everywhere() -> None:
    """Structured outputs require closed objects; a loose object would let the
    model drift from AgentFindings and break parsing."""
    _assert_strict(REPORT_JSON_SCHEMA)
    assert REPORT_JSON_SCHEMA["properties"]["risk_rating"]["enum"] == ["LOW", "MEDIUM", "HIGH"]
