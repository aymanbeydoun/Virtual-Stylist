"""End-to-end flow: upload → ingest → generate outfit → record event.

Exercises the full Postgres + pgvector schema, the typed JSON columns, the
ingest worker run inline, and the stylist engine with rule validation.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image


def _solid_jpeg(hex_color: str) -> bytes:
    """Generate a synthetic test JPEG that passes preflight_check.

    Preflight rejects images below 256x256 or with Laplacian variance under
    60 (too blurry). A purely solid color has variance 0, so we lay a faint
    pseudo-random noise pattern over the base colour — variance > 60, but
    visually still recognisable as the colour, and deterministic per seed.
    """
    import numpy as np

    rgb = tuple(int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    rng = np.random.default_rng(seed=hash(hex_color) & 0xFFFFFFFF)
    noise = rng.integers(-30, 30, size=(256, 256, 3), dtype=np.int16)
    base = np.array(rgb, dtype=np.int16)[None, None, :]
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _upload_item(client: TestClient, headers: dict[str, str], hex_color: str) -> dict:
    signed = client.post(
        "/api/v1/wardrobe/upload-url",
        headers=headers,
        json={"content_type": "image/jpeg", "owner_kind": "user"},
    )
    assert signed.status_code == 200, signed.text
    payload = signed.json()

    put = client.put(
        payload["upload_url"],
        files={"file": ("item.jpg", _solid_jpeg(hex_color), "image/jpeg")},
    )
    assert put.status_code == 200, put.text

    created = client.post(
        "/api/v1/wardrobe/items",
        headers=headers,
        json={"object_key": payload["object_key"], "owner_kind": "user"},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_wardrobe_upload_lists_and_tags(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    item = _upload_item(client, auth_headers, "#123456")
    assert item["status"] == "ready"
    assert item["category"]
    assert item["pattern"] in {"solid", "stripe", "floral", "graphic", "plaid", "other"}
    assert isinstance(item["colors"], list) and len(item["colors"]) >= 1
    assert item["colors"][0]["hex"].startswith("#")

    listed = client.get("/api/v1/wardrobe/items", headers=auth_headers)
    assert listed.status_code == 200
    ids = [i["id"] for i in listed.json()]
    assert item["id"] in ids


def test_correct_item_tag_clears_review_flag(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    item = _upload_item(client, auth_headers, "#abcdef")
    resp = client.post(
        f"/api/v1/wardrobe/items/{item['id']}/corrections",
        headers=auth_headers,
        json={"field": "category", "new_value": "womens.tops.blouse"},
    )
    assert resp.status_code == 204

    fetched = client.get(f"/api/v1/wardrobe/items/{item['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["category"] == "womens.tops.blouse"
    assert body["needs_review"] is False


def test_stylist_generate_returns_outfits_or_empty(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    # Seed enough items across slots for the validator to find a valid outfit.
    for hex_color in ["#1c2541", "#f5e1c8", "#1f3a68", "#0c0c0c", "#f4f4f5"]:
        _upload_item(client, auth_headers, hex_color)

    resp = client.post(
        "/api/v1/stylist/generate",
        headers=auth_headers,
        json={"destination": "office", "mood": "confident"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "outfits" in body
    assert "weather" in body
    if body["weather"]:
        assert {"temp_c", "condition", "wind_kph", "source"} <= body["weather"].keys()


def test_family_member_creation_requires_consent_for_kid(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    no_consent = client.post(
        "/api/v1/family/members",
        headers=auth_headers,
        json={"display_name": "Ava", "kind": "kid", "birth_year": 2017},
    )
    assert no_consent.status_code == 400

    with_consent = client.post(
        "/api/v1/family/members",
        headers=auth_headers,
        json={
            "display_name": "Ava",
            "kind": "kid",
            "birth_year": 2017,
            "consent_method": "card_check",
        },
    )
    assert with_consent.status_code == 201
    member = with_consent.json()
    assert member["kind"] == "kid"
    assert member["kid_mode"] is True
