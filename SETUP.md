# SETUP — VS Code + environment

## 1. Get the code
Unzip `modelcost-scaffold.zip` and open the `modelcost` folder in VS Code
(**File → Open Folder**).

## 2. Install extensions
- **Python** (Microsoft) — IntelliSense, debugger, test explorer
- **Jupyter** (Microsoft) — run `notebooks/` inside VS Code

## 3. Create the virtual environment
In VS Code's terminal (`Ctrl+`` `):

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv`.
(The included `.vscode/settings.json` already points VS Code at `.venv` and
enables pytest discovery.)

## 4. How you'll work in VS Code
- **Experiments** → `notebooks/` (chunking comparison, embedding shootout).
  Pick the `.venv` kernel top-right in the notebook toolbar.
- **Pipeline code** → `src/modelcost/...` — plain Python modules, imported by
  notebooks and tests.
- **Tests** → `tests/` — run via the Testing panel (flask icon) or `pytest`.
- **Debug** → set breakpoints, F5. Use this on the retrieval path — stepping
  through ANN search + rerank teaches more than any doc.

## 5. GPU for fine-tuning (Kaggle — free, 30 hrs/week)
1. Create an account at kaggle.com and verify your phone number (unlocks GPU).
2. We develop training code locally, then run it in a Kaggle notebook with
   **Accelerator: GPU T4** selected (right-hand panel).
3. Upload `data/processed/qa_pairs.jsonl` as a Kaggle dataset, or paste the
   training script into a notebook — I'll walk you through it in Phase 3.

## 6. Accounts you'll need (all free)
- Hugging Face (model + dataset hosting, Spaces demo)
- Weights & Biases (experiment tracking) — or use local MLflow
- OpenRouter (only when we run the cost-engine benchmark; ~$3–8 per company)

## 7. Ollama (local LLM, free)
Install from ollama.com, then: `ollama pull llama3.2`
Used for RAG generation and as the eval judge — $0 in API spend.

## 8. Git
```bash
git init && git add -A && git commit -m "scaffold"
```
Push to GitHub when ready — interviewers *will* open this repo.
