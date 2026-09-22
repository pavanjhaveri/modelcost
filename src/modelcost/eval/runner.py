"""Eval runner: company FAQ questions -> candidate models -> accuracy + tokens.

For each candidate model: ask every FAQ question, check how many of the
question's key facts appear in the answer (deterministic, no judge needed),
and record the real token usage OpenRouter reports. Output is a report JSON
that the web app reads — no token-count inputs anywhere.

Usage:
  PYTHONPATH=src python -m modelcost.eval.runner --tenant hostinger
  PYTHONPATH=src python -m modelcost.eval.runner --tenant hostinger --max-questions 2

Auth: OpenRouter API key stored as the `custom.openrouter` connector in the
Secure Vault. This code never sees the key: a surrogate goes in the
Authorization header and is swapped for the real key at egress.
"""
import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import add_surrogate_to_request, read_response_body  # noqa: E402

from modelcost.app.app import match_candidate  # noqa: E402
from modelcost.cost.pricing import fetch_openrouter_catalog  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
CRED = "custom.openrouter"
HOSTS = ["openrouter.ai"]
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT = 90


def load_questions(tenant_id):
    path = REPO / "data" / "raw" / f"{tenant_id}_dataset.json"
    data = json.loads(path.read_text())
    return [
        {"id": q["id"], "question": q["question"],
         "key_facts": q.get("key_facts", [])}
        for q in data["questions"]
    ]


STOPWORDS = {
    "a", "an", "the", "at", "to", "of", "for", "with", "on", "in", "is",
    "are", "be", "and", "or", "it", "its", "your", "you", "by", "as",
    "from", "that", "this", "will", "if", "do", "does",
}


def _stem(word):
    for suffix in ("ational", "tional", "ing", "ed", "ly", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _fact_words(fact):
    return [
        w for w in re.findall(r"[a-z0-9]+", fact.lower())
        if w not in STOPWORDS
    ]


def score_answer(answer, key_facts):
    """Fraction of key facts covered.

    A fact counts as covered when every significant word in it appears in
    the answer (word-boundary, stemmed, case-insensitive) — so "installed
    automatically" and "automatic installation" both satisfy the fact
    "automatically installed". Still deterministic, no judge model needed.
    """
    if not key_facts:
        return 1.0
    text = (answer or "").lower()
    hits = 0
    for fact in key_facts:
        words = _fact_words(fact)
        if words and all(re.search(r"\b" + re.escape(_stem(w)), text) for w in words):
            hits += 1
    return hits / len(key_facts)


def chat(model_id, system, user):
    """One OpenRouter chat call. Returns (text, prompt_tokens, completion_tokens)."""
    body = json.dumps({
        "model": model_id,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }).encode()
    req = urllib.request.Request(CHAT_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("HTTP-Referer", "https://github.com/pavanjhaveri/modelcost")
    req.add_header("X-Title", "ModelCost eval")
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
        payload = json.loads(read_response_body(resp))
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detail}")
    choice = payload["choices"][0]["message"]["content"] or ""
    usage = payload.get("usage", {}) or {}
    return choice, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


def evaluate_tenant(tenant_id, chat_fn=None, max_questions=None, price_catalog=None):
    """Run the eval. chat_fn(model_id, system, user) -> (text, in_tok, out_tok).

    chat_fn is injectable so tests don't hit the network.
    """
    questions = load_questions(tenant_id)
    if max_questions:
        questions = questions[:max_questions]

    catalog = price_catalog if price_catalog is not None else fetch_openrouter_catalog(
        cache_path=REPO / "data" / "processed" / "openrouter_prices.json")
    price_by_id = {m["id"]: (m["input_per_1m"], m["output_per_1m"]) for m in catalog}

    import yaml  # local import: cheap, and keeps module import light
    cfg = yaml.safe_load((REPO / "configs" / f"{tenant_id}.yaml").read_text())
    company = (cfg.get("tenant") or {}).get("name", tenant_id)
    quality_bar = float((cfg.get("quality_bar") or 0.90))
    candidates = (cfg.get("models") or {}).get("cost_candidates") or []
    monthly_queries = int((cfg.get("volume") or {}).get("monthly_queries") or 100000)
    system = (f"You are a helpful customer support agent for {company}. "
              f"Answer the customer's question concisely and accurately.")

    call = chat_fn or (lambda m, s, u: (*chat(m, s, u), None))
    models_report = []
    for cand in candidates:
        resolved = match_candidate(catalog, cand, callable_only=True)
        if resolved is None:
            models_report.append({"candidate": cand, "resolved_id": None,
                                  "error": "not in price catalog"})
            continue
        mid = resolved["id"]
        scores, in_toks, out_toks, latencies, errors = [], [], [], [], 0
        for q in questions:
            t0 = time.time()
            try:
                text, itok, otok = call(mid, system, q["question"])[:3]
                latencies.append(time.time() - t0)
                scores.append(score_answer(text, q["key_facts"]))
                in_toks.append(itok)
                out_toks.append(otok)
            except Exception as e:  # noqa: BLE001 - one bad call must not kill the run
                errors += 1
                latencies.append(time.time() - t0)
                print(f"  [{mid}] {q['id']} failed: {e}")
            time.sleep(0.3)  # be polite to the API
        n = len(scores)
        in_price, out_price = price_by_id[mid]
        eval_cost = sum(
            (i * in_price + o * out_price) / 1e6
            for i, o in zip(in_toks, out_toks))
        models_report.append({
            "candidate": cand,
            "resolved_id": mid,
            "n_answered": n,
            "n_errors": errors,
            "accuracy": round(sum(scores) / n, 4) if n else 0.0,
            "avg_input_tokens": round(sum(in_toks) / n, 1) if n else 0,
            "avg_output_tokens": round(sum(out_toks) / n, 1) if n else 0,
            "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            "eval_cost_usd": round(eval_cost, 4),
        })
        print(f"  [{mid}] accuracy={models_report[-1]['accuracy']} "
              f"tokens={models_report[-1]['avg_input_tokens']}/{models_report[-1]['avg_output_tokens']} "
              f"errors={errors} eval_cost=${eval_cost:.4f}")

    return {
        "tenant": tenant_id,
        "company": company,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_questions": len(questions),
        "monthly_queries": monthly_queries,
        "quality_bar": quality_bar,
        "models": models_report,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-questions", type=int, default=None)
    args = ap.parse_args()

    print(f"Evaluating tenant '{args.tenant}' via OpenRouter...")
    report = evaluate_tenant(args.tenant, max_questions=args.max_questions)
    out = Path(args.out) if args.out else REPO / "docs" / "reports" / f"{args.tenant}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    total = sum(m.get("eval_cost_usd", 0) for m in report["models"])
    print(f"Report -> {out}  (this eval run cost ~${total:.4f} in API usage)")


if __name__ == "__main__":
    main()
