// Tests the page's client-side logic: candidate matching + report-driven
// ranking with a quality bar. Run: node webapp/test_page_logic.mjs
import assert from "node:assert";

// --- copied from webapp/build.py's <script> (keep in sync) ---
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
// --- ranking logic mirrors the page's analyze handler ---
function rank(report, catalog){
  const bar = report.quality_bar || 0.9;
  const rows = [];
  for (const m of report.models){
    if (!m.resolved_id) continue;
    const price = matchCandidate(catalog, m.resolved_id);
    if (!price) continue;
    const perReq = (m.avg_input_tokens * price.input_per_1m +
                    m.avg_output_tokens * price.output_per_1m) / 1e6;
    rows.push({id: m.resolved_id, accuracy: m.accuracy,
               month: perReq * report.monthly_queries, ok: m.accuracy >= bar});
  }
  rows.sort((a,b) => a.month - b.month);
  return {rows, winner: rows.find(r => r.ok) || null};
}

const CATALOG = [
  {id: "openai/gpt-4o-mini", input_per_1m: 0.15, output_per_1m: 0.60},
  {id: "google/gemini-2.5-flash-lite", input_per_1m: 0.10, output_per_1m: 0.40},
  {id: "anthropic/claude-3-haiku", input_per_1m: 1.00, output_per_1m: 5.00},
];
const REPORT = {
  quality_bar: 0.9, monthly_queries: 100000,
  models: [
    {candidate: "a", resolved_id: "google/gemini-2.5-flash-lite",
     accuracy: 0.95, avg_input_tokens: 60, avg_output_tokens: 150},
    {candidate: "b", resolved_id: "openai/gpt-4o-mini",
     accuracy: 0.97, avg_input_tokens: 60, avg_output_tokens: 200},
    {candidate: "c", resolved_id: "anthropic/claude-3-haiku",
     accuracy: 0.50, avg_input_tokens: 60, avg_output_tokens: 150},
  ],
};

// exact id from eval report matches live catalog
assert.equal(matchCandidate(CATALOG, "openai/gpt-4o-mini").id, "openai/gpt-4o-mini");

const {rows, winner} = rank(REPORT, CATALOG);
assert.equal(rows.length, 3);
// gemini cheapest per measured tokens: (60*.10+150*.40)/1e6*1e5 = $0.0066*1e5... check order
assert.equal(rows[0].id, "google/gemini-2.5-flash-lite");
assert.equal(winner.id, "google/gemini-2.5-flash-lite",
  "winner is cheapest model meeting the bar");

// cheapest overall fails the bar -> winner is next cheapest that passes
const REPORT2 = JSON.parse(JSON.stringify(REPORT));
REPORT2.models[0].accuracy = 0.10;
const r2 = rank(REPORT2, CATALOG);
assert.equal(r2.rows[0].id, "google/gemini-2.5-flash-lite");
assert.equal(r2.winner.id, "openai/gpt-4o-mini",
  "below-bar model is skipped for the recommendation");

// nobody passes -> no winner
const REPORT3 = JSON.parse(JSON.stringify(REPORT));
REPORT3.models.forEach(m => m.accuracy = 0.1);
assert.equal(rank(REPORT3, CATALOG).winner, null);

// measured tokens drive cost, not assumed ones
const cheap = rows[0];
const expected = (60 * 0.10 + 150 * 0.40) / 1e6 * 100000;
assert.ok(Math.abs(cheap.month - expected) < 1e-9);

console.log("ALL JS LOGIC TESTS PASSED");
