# LEARNING.md — the study guide

How this works: **you write the code, I teach and review.** Each phase has
concepts to own, a hands-on task, and interview questions you must be able to
answer cold. Don't move to the next phase until you can.

## Phase 0 — Setup & tools (you are here)

Concepts: virtual environments (dependency isolation), why we pin CPU builds
locally and train on Kaggle (free T4, 30 hrs/week), what each library does
(see requirements.txt comments).

Task: finish SETUP.md on your machine, run `python -c "import faiss,
sentence_transformers; print('ok')"`.

Interview Qs: "Why a venv?" / "Why not train on your laptop?"

## Phase 1 — Ingestion (generic connectors + Hostinger corpus)

Concepts:
- **Connector abstraction**: CSV / URL list / sitemap / API all normalize into
  one schema `{tenant_id, doc_id, title, text, url, updated_at}`. Downstream ML
  code never knows the source type.
- **Boilerplate removal**: nav bars, cookie banners, footers poison chunks.
  trafilatura extracts article text; learn what it strips and why.
- **Dedup + hashing**: SHA-256 of normalized text → duplicate detection and
  later incremental sync (only re-embed changed docs).
- **Tenant isolation**: per-company namespaces from day one. Company A's docs
  must never leak into Company B's answers (correctness + privacy).

Task: write `data_pipeline/connectors.py` (faq_json + url_list connectors) and
`data_pipeline/clean.py`. Output: `data/processed/corpus.jsonl`, one JSON per
line in the normalized schema. Start from `data/raw/hostinger_dataset.json`.

Interview Qs: "Why not just feed raw HTML to the embedder?" /
"How do you onboard a company with zero engineering effort?" /
"What breaks when two tenants share one index?"

## Phase 2 — RAG (planned)

Chunking strategies compared by measured retrieval recall; embeddings shootout
(MiniLM vs bge vs e5); FAISS ANN (Flat vs IVF vs HNSW); hybrid dense+BM25 with
reciprocal rank fusion; cross-encoder rerank; grounded generation prompts;
indirect prompt injection.

## Phase 3 — Fine-tuning (planned)

Q/A synthesis from docs (coverage, dedup, leakage control — eval set carved out
FIRST); LoRA/QLoRA on Kaggle; rank selection; catastrophic forgetting;
RAG (knowledge) vs fine-tuning (behavior).

## Phase 4 — Ablation (planned)

base vs RAG vs FT vs RAG+FT on the same held-out set. Prove each piece earned
its place.

## Phase 5 — Evals & robustness (planned)

Retrieval: context recall/precision, hit@k, MRR. Generation: faithfulness,
answer relevancy, BERTScore, blinded LLM judge. Robustness: paraphrase
metamorphic tests, typos, jailbreaks, out-of-domain → "I don't know",
p50/p95 latency.

## Phase 6 — Cost engine (planned)

Token accounting per model, live price tables, $/month at company volume,
cheapest-qualified-model rule, scheduled re-runs (model + price drift).

## Phase 7 — Ship (planned)

pytest CI gate (scores drop → build fails), Gradio demo on HF Spaces,
tenant #2 to prove genericity, README as an FDE case study.
