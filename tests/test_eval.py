"""Tests for the eval runner. No network: chat_fn is injected."""
from modelcost.eval.runner import evaluate_tenant, load_questions, score_answer

FAKE_CATALOG = [
    {"id": "openai/gpt-4o-mini", "name": "mini",
     "input_per_1m": 0.15, "output_per_1m": 0.60},
    {"id": "anthropic/claude-3-haiku", "name": "haiku",
     "input_per_1m": 1.00, "output_per_1m": 5.00},
    {"id": "google/gemini-2.5-flash-lite", "name": "flash",
     "input_per_1m": 0.10, "output_per_1m": 0.40},
    {"id": "meta-llama/llama-3.3-70b-instruct", "name": "llama",
     "input_per_1m": 0.35, "output_per_1m": 0.40},
    {"id": "qwen/qwen-2.5-72b-instruct", "name": "qwen",
     "input_per_1m": 0.35, "output_per_1m": 0.40},
]


def test_load_questions():
    qs = load_questions("hostinger")
    assert len(qs) == 16
    assert all(q["key_facts"] for q in qs)


def test_score_answer():
    assert score_answer("Lifetime SSL is automatically installed", ["automatically installed", "Lifetime SSL"]) == 1.0
    assert score_answer("lifetime ssl here", ["Lifetime SSL", "missing fact"]) == 0.5
    assert score_answer("", ["anything"]) == 0.0
    assert score_answer("whatever", []) == 1.0  # no facts to check: vacuous pass


def fake_chat_factory(answers):
    def fake_chat(model_id, system, user):
        return answers.get(model_id, ("I don't know", 100, 50))
    return fake_chat


def test_evaluate_aggregates():
    # gpt-4o-mini answers contain the SSL facts; haiku does not
    answers = {
        "openai/gpt-4o-mini": ("Lifetime SSL is automatically installed for sites hosted at Hostinger", 800, 300),
        "anthropic/claude-3-haiku": ("I don't know", 800, 300),
        "google/gemini-2.5-flash-lite": ("Lifetime SSL is automatically installed for sites hosted at Hostinger", 800, 300),
        "meta-llama/llama-3.3-70b-instruct": ("Lifetime SSL is automatically installed for sites hosted at Hostinger", 800, 300),
        "qwen/qwen-2.5-72b-instruct": ("Lifetime SSL is automatically installed for sites hosted at Hostinger", 800, 300),
    }
    report = evaluate_tenant(
        "hostinger",
        chat_fn=fake_chat_factory(answers),
        max_questions=1,  # ssl-01: key facts below are all in the fake answer
        price_catalog=FAKE_CATALOG,
    )
    assert report["tenant"] == "hostinger"
    assert report["n_questions"] == 1
    assert report["quality_bar"] == 0.90
    by_id = {m["resolved_id"]: m for m in report["models"]}
    assert by_id["openai/gpt-4o-mini"]["accuracy"] == 1.0
    assert by_id["anthropic/claude-3-haiku"]["accuracy"] == 0.0
    m = by_id["openai/gpt-4o-mini"]
    assert m["avg_input_tokens"] == 800 and m["avg_output_tokens"] == 300
    assert m["n_answered"] == 1 and m["n_errors"] == 0
    # eval cost = 1 * (800*0.15 + 300*0.60)/1e6
    assert m["eval_cost_usd"] == round((800 * 0.15 + 300 * 0.60) / 1e6, 4)


def test_model_errors_dont_kill_run():
    def boom(model_id, system, user):
        raise RuntimeError("API down")
    report = evaluate_tenant("hostinger", chat_fn=boom,
                             max_questions=1, price_catalog=FAKE_CATALOG)
    m = report["models"][0]
    assert m["n_answered"] == 0 and m["n_errors"] == 1
    assert m["accuracy"] == 0.0
