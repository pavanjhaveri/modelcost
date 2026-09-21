"""Tests for price normalization. No network: feed a fake OpenRouter payload."""
from modelcost.cost.pricing import normalize_openrouter_payload

FAKE_PAYLOAD = {
    "data": [
        {
            "id": "acme/spark-1",
            "name": "Acme Spark 1",
            # OpenRouter quotes USD *per token* as strings
            "pricing": {"prompt": "0.000001", "completion": "0.000004"},
        },
        {
            "id": "acme/free-1",
            "name": "Acme Free",
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "acme/broken-1",
            "name": "Acme Broken",
            "pricing": {"prompt": "n/a", "completion": "n/a"},
        },
        {
            "id": "acme/noprice-1",
            "name": "Acme NoPrice",
        },
    ]
}


def test_per_token_strings_become_per_million_floats():
    (m,) = [x for x in normalize_openrouter_payload(FAKE_PAYLOAD) if x["id"] == "acme/spark-1"]
    assert m["input_per_1m"] == 1.0    # 0.000001 * 1e6
    assert m["output_per_1m"] == 4.0   # 0.000004 * 1e6
    assert m["name"] == "Acme Spark 1"


def test_free_malformed_and_unpriced_models_are_skipped():
    ids = {x["id"] for x in normalize_openrouter_payload(FAKE_PAYLOAD)}
    assert ids == {"acme/spark-1"}
