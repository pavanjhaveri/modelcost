"""Demo: fetch live prices, rank models for a sample workload.

Run:  PYTHONPATH=src python -m modelcost.cost.demo
"""
from pathlib import Path

from .calculator import Workload, rank_models
from .pricing import fetch_openrouter_catalog

CACHE = Path("data/processed/openrouter_prices.json")

# Sample workload: 10k support answers/day, ~800-token prompts, ~300-token replies.
SAMPLE_WORKLOAD = Workload(
    requests_per_day=10_000, avg_input_tokens=800, avg_output_tokens=300
)


def main():
    catalog = fetch_openrouter_catalog(cache_path=CACHE)
    print(f"priced models: {len(catalog)}")
    w = SAMPLE_WORKLOAD
    print(
        f"workload: {w.requests_per_day:,} req/day, "
        f"{w.avg_input_tokens} in / {w.avg_output_tokens} out tokens\n"
    )
    ranked = rank_models(catalog, w)
    print(f"{'rank':<4} {'model':<45} {'$/mo':>10}")
    print("-" * 62)
    for i, r in enumerate(ranked[:15], 1):
        print(f"{i:<4} {r['id'][:43]:<45} {r['monthly_cost']:>10.2f}")


if __name__ == "__main__":
    main()
