"""Tests for the cost math. Fake 2-model catalog, hand-computed expectations.

Model A: flat $2/1M in, $2/1M out.
Model B: cheap input $0.5/1M, expensive output $8/1M.

The point of the flip test: the cheapest model DEPENDS ON THE WORKLOAD.
Input-heavy  -> B wins.  Output-heavy -> A wins.
Anyone who hardcodes "cheapest model" without a workload is wrong.
"""
from modelcost.cost.calculator import Workload, cost_per_request, monthly_cost, rank_models

CATALOG = [
    {"id": "model-a", "name": "Model A", "input_per_1m": 2.0, "output_per_1m": 2.0},
    {"id": "model-b", "name": "Model B", "input_per_1m": 0.5, "output_per_1m": 8.0},
]


def test_cost_per_request_math():
    w = Workload(requests_per_day=1_000, avg_input_tokens=2_000, avg_output_tokens=100)
    # A: (2000*2 + 100*2)/1e6 = 4200/1e6 = 0.0042
    assert cost_per_request(w, CATALOG[0]) == 0.0042
    # B: (2000*0.5 + 100*8)/1e6 = 1800/1e6 = 0.0018
    assert cost_per_request(w, CATALOG[1]) == 0.0018


def test_monthly_cost_scales_with_volume():
    w = Workload(requests_per_day=1_000, avg_input_tokens=2_000, avg_output_tokens=100)
    # 0.0042 * 1000 * 30 = 126.0
    assert monthly_cost(w, CATALOG[0]) == 126.0


def test_ranking_flips_with_workload_shape():
    input_heavy = Workload(requests_per_day=1_000, avg_input_tokens=2_000, avg_output_tokens=100)
    output_heavy = Workload(requests_per_day=1_000, avg_input_tokens=100, avg_output_tokens=2_000)

    assert rank_models(CATALOG, input_heavy)[0]["id"] == "model-b"   # cheap input wins
    assert rank_models(CATALOG, output_heavy)[0]["id"] == "model-a"  # cheap output wins


def test_ranked_entries_carry_all_cost_fields():
    w = Workload(requests_per_day=100, avg_input_tokens=500, avg_output_tokens=500)
    top = rank_models(CATALOG, w)[0]
    assert top["daily_cost"] == top["cost_per_request"] * 100
    assert top["monthly_cost"] == top["daily_cost"] * 30
