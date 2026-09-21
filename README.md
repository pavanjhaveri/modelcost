# ModelCost

A **generic, multi-tenant platform** that turns any company's FAQs/docs into a tuned
support assistant — and tells them the cheapest LLM that clears their quality bar.

Flow: **ingest company FAQs → build RAG + fine-tune on their Q/A → evaluate quality
per model → estimate cost at their volume → recommend cheapest model ≥ quality bar →
re-run on schedule as models/prices change.**

Company #1 (vertical slice): Hostinger. Then we abstract to any tenant.

## Architecture

```
Company A ──┐
Company B ──┼──► Ingestion ──► normalized corpus (tenant-isolated)
Company C ──┘    (CSV / URLs / sitemap / API)
                        │
                        ▼
                 clean → chunk → embed → FAISS index   (per-tenant namespace)
                        │
                        ▼
                 Q/A synthesis (docs → training pairs, leakage-controlled)
                        │
                        ▼
                 model track: base / RAG / fine-tuned / RAG+fine-tuned
                        │      × candidate models
                        ▼
                 evaluation: retrieval + generation + robustness metrics
                        │
                        ▼
                 cost engine: tokens × volume × price → $/month per model
                        │
                        ▼
                 recommendation + scheduled re-runs + per-company report
```

## Repo map

| Path | What lives here |
|---|---|
| `configs/` | one YAML per company (tenant) |
| `src/modelcost/data_pipeline/` | ingestion connectors, cleaning, chunking |
| `src/modelcost/rag/` | embeddings, FAISS index, hybrid retrieval, rerank, generation |
| `src/modelcost/finetune/` | Q/A synthesis, LoRA/QLoRA training configs |
| `src/modelcost/evals/` | retrieval / generation / robustness metrics, judges |
| `src/modelcost/app/` | Gradio demo (HF Spaces) |
| `notebooks/` | experiments (chunking comparison, embedding comparison ...) |
| `tests/` | pytest suite = the CI quality gate |
| `LEARNING.md` | **start here** — the study guide: concepts per phase + interview Qs |
| `SETUP.md` | VS Code + venv + Kaggle setup |

## Roadmap

- [ ] Phase 1 — ingestion: generic connectors + Hostinger corpus
- [ ] Phase 2 — RAG: embeddings, FAISS, hybrid retrieval, reranking
- [ ] Phase 3 — fine-tuning: Q/A synthesis + LoRA/QLoRA on Kaggle
- [ ] Phase 4 — ablation: base vs RAG vs FT vs RAG+FT, measured
- [ ] Phase 5 — evals: retrieval / generation / robustness harness
- [ ] Phase 6 — cost engine + recommendation report
- [ ] Phase 7 — CI gate, HF Spaces demo, tenant #2

## Cost

$0 in fixed costs (all open-source + free tiers). Only variable spend is the
multi-model benchmark via API ≈ **$3–8 per company run**. Training is free on
Kaggle (30 GPU-hrs/week). See `LEARNING.md` Phase 0 for the full breakdown.
