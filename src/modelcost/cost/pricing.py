"""Live model price catalog.

Key decision: prices are fetched at runtime, never hardcoded.
LLM prices change every few weeks (providers cut them constantly),
so a hardcoded table is stale the day you write it.

Source: OpenRouter's public model list (free, no API key). It aggregates
100+ models across providers into one normalized price feed.
"""
import json
import time
from pathlib import Path

import requests

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE_TTL_SECONDS = 24 * 3600  # prices move weekly; daily refresh is plenty


def normalize_openrouter_payload(payload):
    """OpenRouter JSON -> [{id, name, input_per_1m, output_per_1m}, ...].

    Pure function (no network) so it's trivially unit-testable.
    OpenRouter quotes pricing as *strings* in USD per single token,
    e.g. "0.000001" -> $1.00 per 1M tokens.
    """
    catalog = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            per_token_in = float(pricing.get("prompt") or 0)
            per_token_out = float(pricing.get("completion") or 0)
        except (TypeError, ValueError):
            continue  # malformed pricing entry; skip, don't crash the run
        if per_token_in <= 0 and per_token_out <= 0:
            continue  # free or unpriced model — not comparable, skip
        catalog.append(
            {
                "id": m["id"],
                "name": m.get("name") or m["id"],
                "input_per_1m": per_token_in * 1_000_000,
                "output_per_1m": per_token_out * 1_000_000,
            }
        )
    return catalog


def fetch_openrouter_catalog(cache_path=None, ttl_seconds=CACHE_TTL_SECONDS):
    """Fetch the live catalog, using a JSON cache file when it's fresh.

    cache_path: e.g. Path("data/processed/openrouter_prices.json").
    Returns the normalized catalog list.
    """
    if cache_path is not None:
        cache_path = Path(cache_path)
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text())
                age = time.time() - cached.get("fetched_at", 0)
                if age < ttl_seconds and cached.get("models"):
                    return cached["models"]
            except (json.JSONDecodeError, OSError):
                pass  # corrupt cache -> just refetch

    resp = requests.get(OPENROUTER_MODELS_URL, timeout=30)
    resp.raise_for_status()  # clear error instead of silently bad data
    catalog = normalize_openrouter_payload(resp.json())

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"fetched_at": time.time(), "models": catalog})
        )
    return catalog
