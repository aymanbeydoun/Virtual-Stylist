from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings

_CACHE: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_TTL_SECONDS = 15 * 60


def _round_coord(value: float) -> float:
    # 5km bucket for privacy + cache hit rate
    return round(value, 1)


async def get_weather(lat: float | None, lon: float | None) -> dict[str, Any] | None:
    if lat is None or lon is None:
        return None
    key = (_round_coord(lat), _round_coord(lon))
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]

    settings = get_settings()
    if not settings.openweather_api_key:
        snapshot = {"temp_c": 22.0, "condition": "clear", "wind_kph": 5.0, "source": "stub"}
        _CACHE[key] = (now, snapshot)
        return snapshot

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "lat": key[0],
                "lon": key[1],
                "appid": settings.openweather_api_key,
                "units": "metric",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        snapshot = {
            "temp_c": data["main"]["temp"],
            "condition": data["weather"][0]["main"].lower(),
            "wind_kph": data["wind"]["speed"] * 3.6,
            "source": "openweather",
        }
        _CACHE[key] = (now, snapshot)
        return snapshot
