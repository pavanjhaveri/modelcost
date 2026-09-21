"""Workload -> dollars. Pure math, no network, no I/O.

This is deliberately separated from pricing.py: the math never changes,
the prices change weekly. Separation = the math is trivially testable
with a fake 2-model catalog and hand-computed expectations.
"""
from dataclasses import dataclass

TOKENS_PER_MILLION = 1_000_000
DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Workload:
    """Everything needed to price a workload. All from *your* measurements.

    requests_per_day: e.g. support tickets/day, or API calls/day
    avg_input_tokens:  measured mean prompt tokens per request
    avg_output_tokens: measured mean completion tokens per request
    """

    requests_per_day: int
    avg_input_tokens: int
    avg_output_tokens: int


def cost_per_request(workload, price):
    """USD for one request on one model.

    price: {"input_per_1m": float, "output_per_1m": float} in USD.
    """
    tokens_cost = (
        workload.avg_input_tokens * price["input_per_1m"]
        + workload.avg_output_tokens * price["output_per_1m"]
    )
    return tokens_cost / TOKENS_PER_MILLION


def monthly_cost(workload, price):
    """USD per 30-day month for the whole workload on one model."""
    return cost_per_request(workload, price) * workload.requests_per_day * DAYS_PER_MONTH


def rank_models(catalog, workload):
    """Cheapest-first ranking of every model for this workload.

    Returns [{id, name, input_per_1m, output_per_1m,
              cost_per_request, daily_cost, monthly_cost}, ...]
    sorted by monthly_cost ascending.
    """
    ranked = []
    for m in catalog:
        cpr = cost_per_request(workload, m)
        ranked.append(
            {
                "id": m["id"],
                "name": m["name"],
                "input_per_1m": m["input_per_1m"],
                "output_per_1m": m["output_per_1m"],
                "cost_per_request": cpr,
                "daily_cost": cpr * workload.requests_per_day,
                "monthly_cost": cpr * workload.requests_per_day * DAYS_PER_MONTH,
            }
        )
    ranked.sort(key=lambda r: r["monthly_cost"])
    return ranked
