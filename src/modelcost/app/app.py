"""Web UI: enter a company name -> cheapest models for its workload.

Run:  PYTHONPATH=src python -m modelcost.app.app
Then open the printed http://127.0.0.1:7860 URL in your browser.
"""
from pathlib import Path

import yaml

from modelcost.cost.calculator import Workload, rank_models
from modelcost.cost.pricing import fetch_openrouter_catalog

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_DIR = REPO_ROOT / "configs"
CACHE_PATH = REPO_ROOT / "data" / "processed" / "openrouter_prices.json"

DEFAULT_AVG_INPUT_TOKENS = 800
DEFAULT_AVG_OUTPUT_TOKENS = 300


def list_tenants():
    """Tenant ids from configs/*.yaml — adding a company = adding a file."""
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.yaml"))


def load_tenant(company_name):
    key = company_name.strip().lower()
    path = CONFIGS_DIR / f"{key}.yaml"
    if not path.exists():
        raise ValueError(
            f"Unknown company '{company_name}'. "
            f"Available: {', '.join(list_tenants()) or 'none yet'}"
        )
    with open(path) as f:
        return yaml.safe_load(f)


def _tokens(s):
    import re
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


def _is_subsequence(needle, haystack):
    """All needle tokens appear in haystack in order (not necessarily adjacent)."""
    it = iter(haystack)
    return all(any(tok == h for h in it) for tok in needle)


def match_candidate(catalog, candidate_id, callable_only=False):
    """Map a config model id to a live catalog entry.

    Exact match first; otherwise token-subsequence match on the model name
    (e.g. 'claude-haiku' matches 'anthropic/claude-3-5-haiku' despite the
    version infix), preferring the same provider. Config ids are shorthand —
    the live catalog has the provider-qualified variants.
    """
    for m in catalog:
        if m["id"] == candidate_id:
            if callable_only and m["id"].endswith(":batch"):
                break  # exact id isn't callable; fall through to fuzzy match
            return m
    provider, _, name = candidate_id.partition("/")
    needle = _tokens(name or candidate_id)
    hits = [m for m in catalog if _is_subsequence(needle, _tokens(m["id"]))]
    if callable_only:
        hits = [m for m in hits if not m["id"].endswith(":batch")]
    if not hits:
        return None
    same_provider = [m for m in hits if m["id"].startswith(provider + "/")]
    pool = same_provider or hits
    return min(pool, key=lambda m: (m["input_per_1m"], m["output_per_1m"]))


def analyze_company(company_name, avg_input_tokens=None, avg_output_tokens=None,
                    catalog=None):
    """Company name -> (headline, workload summary, ranked table, notes).

    catalog is injectable so tests don't need the network.
    Returns plain data; the Gradio wrapper below only renders it.
    """
    cfg = load_tenant(company_name)
    tenant = cfg.get("tenant", {}) or {}
    volume = cfg.get("volume", {}) or {}
    monthly_queries = int(volume.get("monthly_queries") or 0)
    if monthly_queries <= 0:
        raise ValueError(
            f"Tenant '{company_name}' has no volume.monthly_queries set."
        )

    avg_in = int(avg_input_tokens or volume.get("avg_input_tokens")
                 or DEFAULT_AVG_INPUT_TOKENS)
    avg_out = int(avg_output_tokens or volume.get("avg_output_tokens")
                  or DEFAULT_AVG_OUTPUT_TOKENS)
    workload = Workload(
        requests_per_day=monthly_queries // 30,
        avg_input_tokens=avg_in,
        avg_output_tokens=avg_out,
    )

    if catalog is None:
        catalog = fetch_openrouter_catalog(cache_path=CACHE_PATH)

    candidates = (cfg.get("models") or {}).get("cost_candidates") or []
    priced, missing = [], []
    for cand in candidates:
        m = match_candidate(catalog, cand)
        (priced if m else missing).append(m if m else cand)

    ranked = rank_models(priced, workload)
    table = [
        [i + 1, r["id"], f"${r['cost_per_request']:.5f}",
         f"${r['daily_cost']:.2f}", f"${r['monthly_cost']:.2f}"]
        for i, r in enumerate(ranked)
    ]

    headline = (
        f"## Cheapest for {tenant.get('name', company_name)}: "
        f"`{ranked[0]['id']}` at **${ranked[0]['monthly_cost']:.2f}/month**"
        if ranked else "## No priced candidates found"
    )
    summary = (
        f"Workload: **{monthly_queries:,}** queries/month "
        f"({workload.requests_per_day:,}/day), "
        f"{avg_in} input / {avg_out} output tokens per request."
    )
    notes = (
        f"_Not in live price catalog: {', '.join(missing)}_" if missing else ""
    )
    return headline, summary, table, notes


def build_ui():
    import gradio as gr  # lazy: analysis works without the UI dependency

    with gr.Blocks(title="ModelCost") as demo:
        gr.Markdown("# ModelCost — cheapest model for a company's workload")
        company = gr.Textbox(label="Company name", placeholder="hostinger",
                             value="hostinger")
        with gr.Row():
            avg_in = gr.Number(label="Avg input tokens / request",
                               value=DEFAULT_AVG_INPUT_TOKENS, precision=0)
            avg_out = gr.Number(label="Avg output tokens / request",
                                value=DEFAULT_AVG_OUTPUT_TOKENS, precision=0)
        btn = gr.Button("Calculate cheapest models")
        headline = gr.Markdown()
        summary = gr.Markdown()
        table = gr.Dataframe(
            headers=["#", "Model", "$/request", "$/day", "$/month"],
            label="Ranked by monthly cost",
        )
        notes = gr.Markdown()

        def _run(name, ai, ao):
            try:
                return analyze_company(name, ai, ao)
            except Exception as e:  # show config errors in the UI, not a traceback
                return f"**Error:** {e}", "", [], ""

        btn.click(_run, inputs=[company, avg_in, avg_out],
                  outputs=[headline, summary, table, notes])
    return demo


if __name__ == "__main__":
    build_ui().launch()
