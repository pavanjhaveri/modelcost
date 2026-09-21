"""Tests for the company analyzer. No network: inject a fake catalog."""
import pytest

from modelcost.app.app import analyze_company, load_tenant

FAKE_CATALOG = [
    {"id": "openai/gpt-4o-mini", "name": "GPT 4o mini",
     "input_per_1m": 0.15, "output_per_1m": 0.60},
    {"id": "anthropic/claude-3-5-haiku", "name": "Haiku",
     "input_per_1m": 1.00, "output_per_1m": 5.00},
    {"id": "google/gemini-flash-1.5", "name": "Gemini Flash",
     "input_per_1m": 0.35, "output_per_1m": 1.05},
    {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 70B",
     "input_per_1m": 0.35, "output_per_1m": 0.40},
    {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 72B",
     "input_per_1m": 0.35, "output_per_1m": 0.40},
]


def test_hostinger_config_loads():
    cfg = load_tenant("hostinger")
    assert cfg["tenant"]["id"] == "hostinger"
    assert cfg["volume"]["monthly_queries"] == 100_000


def test_unknown_company_lists_available():
    with pytest.raises(ValueError, match="Available"):
        analyze_company("nonexistent-corp", catalog=FAKE_CATALOG)


def test_analyze_ranks_cheapest_first():
    headline, summary, table, notes = analyze_company(
        "hostinger", catalog=FAKE_CATALOG
    )
    assert len(table) == 5  # all 5 cost_candidates matched
    assert table[0][1] == "openai/gpt-4o-mini"
    assert "openai/gpt-4o-mini" in headline
    # monthly costs strictly ascending down the table
    monthly = [float(row[4].replace("$", "")) for row in table]
    assert monthly == sorted(monthly)
    assert "100,000" in summary


def test_fuzzy_candidate_matching():
    # config says "anthropic/claude-haiku"; catalog has "anthropic/claude-3-5-haiku"
    _, _, table, _ = analyze_company("hostinger", catalog=FAKE_CATALOG)
    ids = [row[1] for row in table]
    assert "anthropic/claude-3-5-haiku" in ids


def test_unmatched_candidate_reported_not_crashed():
    catalog = [m for m in FAKE_CATALOG if "qwen" not in m["id"]]
    _, _, table, notes = analyze_company("hostinger", catalog=catalog)
    assert len(table) == 4
    assert "qwen/qwen-2.5-72b" in notes
