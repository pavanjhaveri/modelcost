"""Build the GitHub Pages web app: docs/index.html (single self-contained file).

Reads tenant configs from configs/*.yaml, embeds them plus a price snapshot,
and emits a page that:
  1. fetches the tenant's eval report (docs/reports/<company>.json) —
     accuracy + measured tokens per model, produced by
     `python -m modelcost.eval.runner --tenant <company>`;
  2. fetches LIVE OpenRouter prices in the browser
     (CORS: Access-Control-Allow-Origin: *), falling back to the snapshot;
  3. ranks models by monthly cost and recommends the cheapest one that
     meets the tenant's quality bar.

Usage:  PYTHONPATH=src .venv/bin/python webapp/build.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
CONFIGS = REPO / "configs"
OUT = REPO / "docs" / "index.html"

CATALOG_URL = "https://openrouter.ai/api/v1/models"


def load_tenants():
    tenants = {}
    for path in sorted(CONFIGS.glob("*.yaml")):
        cfg = yaml.safe_load(path.read_text())
        tenant = cfg.get("tenant", {}) or {}
        tenants[path.stem] = {"name": tenant.get("name", path.stem)}
    return tenants


def fetch_snapshot():
    """Current OpenRouter catalog, normalized — embedded as fallback data."""
    import requests

    resp = requests.get(CATALOG_URL, timeout=30)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("data", []):
        try:
            inp = float(m["pricing"]["prompt"]) * 1_000_000
            outp = float(m["pricing"]["completion"]) * 1_000_000
        except (KeyError, TypeError, ValueError):
            continue
        if inp == 0 and outp == 0:
            continue
        out.append({"id": m["id"], "name": m.get("name", m["id"]),
                    "input_per_1m": inp, "output_per_1m": outp})
    return out


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ModelCost — cheapest LLM for your workload</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, -apple-system, sans-serif; background: #0f1115;
         color: #e8eaf0; max-width: 900px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { font-size: 28px; margin: 0 0 4px; }
  .sub { color: #9aa0ae; margin-bottom: 24px; }
  .card { background: #171a21; border: 1px solid #262b36; border-radius: 12px;
          padding: 20px; margin-bottom: 16px; }
  label { display: block; font-size: 13px; color: #9aa0ae; margin: 12px 0 4px; }
  input { width: 100%; box-sizing: border-box; padding: 10px 12px; font-size: 16px;
          background: #0f1115; border: 1px solid #2e3440; border-radius: 8px; color: #fff; }
  button { margin-top: 16px; padding: 12px 24px; font-size: 16px; font-weight: 600;
           background: #4f7cff; color: #fff; border: 0; border-radius: 8px; cursor: pointer; }
  button:hover { background: #3d68e8; }
  button:disabled { opacity: .6; cursor: default; }
  .error { color: #ff8a8a; margin-top: 12px; }
  #headline { font-size: 20px; margin: 0 0 8px; }
  #headline code { color: #7ee2a8; }
  .meta { color: #9aa0ae; font-size: 14px; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 15px; }
  th, td { text-align: left; padding: 10px 8px; border-bottom: 1px solid #262b36; }
  th { color: #9aa0ae; font-weight: 600; font-size: 13px; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  th.num { text-align: right; }
  tr.winner td { color: #7ee2a8; font-weight: 600; }
  tr.failed td.acc { color: #ff8a8a; }
  td.acc { font-variant-numeric: tabular-nums; }
  .badge { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px;
           border-radius: 20px; margin-left: 8px; vertical-align: middle; }
  .badge.ok { background: #1d3a28; color: #7ee2a8; }
  .badge.no { background: #3a1d1d; color: #ff8a8a; }
  .src { margin-top: 24px; font-size: 13px; color: #9aa0ae; }
  .hidden { display: none; }
</style>
</head>
<body>
<h1>ModelCost</h1>
<div class="sub">Cheapest LLM for a company's workload — accuracy measured on real
FAQ questions, prices live from OpenRouter.</div>

<div class="card">
  <label for="company">Company name</label>
  <input id="company" list="tenants" placeholder="hostinger" value="hostinger" autocomplete="off">
  <datalist id="tenants">__DATALIST__</datalist>
  <button id="go">Run cost analysis</button>
  <div id="err" class="error"></div>
</div>

<div id="result" class="card hidden">
  <div id="headline"></div>
  <div id="summary" class="meta"></div>
  <table>
    <thead><tr><th>#</th><th>Model</th><th class="num">Accuracy</th>
    <th class="num">Tokens in/out</th><th class="num">$/month</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <div id="notes" class="meta"></div>
</div>

<div class="src" id="src"></div>

<script>
const TENANTS = __TENANTS_JSON__;
const SNAPSHOT = { as_of: "__SNAPSHOT_DATE__", models: __SNAPSHOT_JSON__ };

function tokens(s){ return s.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean); }
function isSubseq(needle, hay){
  let i = 0;
  for (const t of needle){ let found = false;
    while (i < hay.length){ if (hay[i++] === t){ found = true; break; } }
    if (!found) return false; }
  return true;
}
function matchCandidate(catalog, cid){
  const exact = catalog.find(m => m.id === cid);
  if (exact) return exact;
  const parts = cid.split("/");
  const provider = parts.length > 1 ? parts[0] : cid;
  const name = parts.length > 1 ? parts.slice(1).join("/") : cid;
  const needle = tokens(name);
  const hits = catalog.filter(m => isSubseq(needle, tokens(m.id)));
  if (!hits.length) return null;
  const sameProv = hits.filter(m => m.id.startsWith(provider + "/"));
  const pool = sameProv.length ? sameProv : hits;
  return pool.reduce((a,b) => (a.input_per_1m < b.input_per_1m ||
      (a.input_per_1m === b.input_per_1m && a.output_per_1m <= b.output_per_1m)) ? a : b);
}
function normalizePayload(data){
  const out = [];
  for (const m of (data.data || [])){
    let inp, outp;
    try { inp = parseFloat(m.pricing.prompt) * 1e6;
          outp = parseFloat(m.pricing.completion) * 1e6; }
    catch(e){ continue; }
    if (!isFinite(inp) || !isFinite(outp)) continue;
    if (inp === 0 && outp === 0) continue;
    out.push({id: m.id, name: m.name || m.id, input_per_1m: inp, output_per_1m: outp});
  }
  return out;
}
async function getCatalog(){
  try {
    const r = await fetch("https://openrouter.ai/api/v1/models");
    if (!r.ok) throw new Error("http " + r.status);
    const models = normalizePayload(await r.json());
    if (!models.length) throw new Error("empty");
    document.getElementById("src").textContent =
      "Prices: live from OpenRouter (" + models.length + " models, just now).";
    return models;
  } catch(e){
    document.getElementById("src").textContent =
      "Prices: live fetch failed — snapshot of " + SNAPSHOT.models.length +
      " models from " + SNAPSHOT.as_of + ".";
    return SNAPSHOT.models;
  }
}
function fmt(n, d){ return "$" + n.toFixed(d); }

document.getElementById("go").addEventListener("click", async () => {
  const btn = document.getElementById("go"), err = document.getElementById("err");
  err.textContent = "";
  const key = document.getElementById("company").value.trim().toLowerCase();
  const t = TENANTS[key];
  if (!t){
    const avail = Object.keys(TENANTS).join(", ") || "none yet";
    err.textContent = "Unknown company '" + key + "'. Available: " + avail + ".";
    return;
  }
  btn.disabled = true; btn.textContent = "Loading eval report…";
  let report;
  try {
    const r = await fetch("reports/" + key + ".json");
    if (!r.ok) throw new Error("no report");
    report = await r.json();
  } catch(e){
    err.textContent = "No eval report yet for '" + key + "'. Reports are produced by " +
      "running the FAQ questions against the candidate models: " +
      "python -m modelcost.eval.runner --tenant " + key;
    btn.disabled = false; btn.textContent = "Run cost analysis";
    return;
  }
  btn.textContent = "Fetching prices…";
  try {
    const catalog = await getCatalog();
    const bar = report.quality_bar || 0.9;
    const rows = [];
    const missing = [];
    for (const m of report.models){
      if (!m.resolved_id){ missing.push(m.candidate + " (not in catalog)"); continue; }
      const price = matchCandidate(catalog, m.resolved_id);
      if (!price){ missing.push(m.resolved_id); continue; }
      const perReq = (m.avg_input_tokens * price.input_per_1m +
                      m.avg_output_tokens * price.output_per_1m) / 1e6;
      const month = perReq * report.monthly_queries;
      rows.push({id: m.resolved_id, accuracy: m.accuracy,
                 inTok: m.avg_input_tokens, outTok: m.avg_output_tokens,
                 perReq, month, ok: m.accuracy >= bar});
    }
    rows.sort((a,b) => a.month - b.month);
    const winner = rows.find(r => r.ok) || null;

    const box = document.getElementById("result");
    box.classList.remove("hidden");
    document.getElementById("headline").innerHTML = winner
      ? "Cheapest for " + report.company + " at " +
        Math.round(bar*100) + "% quality bar: <code>" + winner.id +
        "</code> at <b>" + fmt(winner.month, 2) + "/month</b>"
      : "No model met the " + Math.round(bar*100) + "% quality bar.";
    document.getElementById("summary").textContent =
      report.company + ": " + report.monthly_queries.toLocaleString() +
      " queries/month. Accuracy measured on " + report.n_questions +
      " real FAQ questions per model (report " + report.generated_at + "). " +
      "Token counts are measured from those runs — not assumed.";
    document.getElementById("rows").innerHTML = rows.map((r,i) =>
      "<tr class='" + (winner && r.id === winner.id ? "winner" : (r.ok ? "" : "failed")) +
      "'><td>" + (i+1) + "</td><td>" + r.id +
      (winner && r.id === winner.id ? "<span class='badge ok'>RECOMMENDED</span>"
        : (r.ok ? "" : "<span class='badge no'>BELOW BAR</span>")) +
      "</td><td class='num acc'>" + (r.accuracy*100).toFixed(1) + "%</td>" +
      "<td class='num'>" + Math.round(r.inTok) + " / " + Math.round(r.outTok) + "</td>" +
      "<td class='num'>" + fmt(r.month, 2) + "</td></tr>").join("");
    const evalCost = report.models.reduce((s,m) => s + (m.eval_cost_usd || 0), 0);
    document.getElementById("notes").textContent =
      (missing.length ? "Not in live price catalog: " + missing.join(", ") + ". " : "") +
      "Running this eval cost " + fmt(evalCost, 4) + " in API usage.";
    box.scrollIntoView({behavior: "smooth", block: "nearest"});
  } finally {
    btn.disabled = false; btn.textContent = "Run cost analysis";
  }
});
</script>
</body>
</html>
"""


def main():
    tenants = load_tenants()
    try:
        models = fetch_snapshot()
        as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"live snapshot: {len(models)} models")
    except Exception as e:
        print(f"live fetch failed ({e}); embedding empty snapshot")
        models, as_of = [], "never"

    datalist = "".join(
        f'<option value="{k}">{v["name"]}</option>' for k, v in tenants.items()
    )
    html = HTML.replace("__DATALIST__", datalist)
    html = html.replace("__TENANTS_JSON__", json.dumps(tenants))
    html = html.replace("__SNAPSHOT_DATE__", as_of)
    html = html.replace("__SNAPSHOT_JSON__", json.dumps(models))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
