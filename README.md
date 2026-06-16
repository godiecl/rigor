# Rigor

> Automated, rubric-based evaluation of engineering professional-practice reports using an **LLM-as-a-judge** pipeline.

![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

Rigor reads a batch of PDF reports and produces a structured, auditable assessment for each one. Instead of a single model call, it runs **eight specialist judges** — one per rubric criterion — and combines their verdicts into a final weighted grade with evidence, page references, and automatic quality checks.

## What it does

- **Per-criterion specialist judges.** Eight independent agents grade the report against a fixed rubric (1.0–7.0 in 0.5 steps), each with its own prompt and weight.
- **Weighted aggregation.** Scores are combined into a final grade; the level (Excelente / Bueno / Suficiente / Insuficiente) is derived deterministically from the score.
- **Evidence grounding.** Every cited quote is verified to exist verbatim in the document and is mapped back to its **PDF page**; fabricated or unlocatable citations are flagged.
- **Anti-hallucination guardrails.** A shared prompt preamble enforces scope, grounding, and calibration; structural failsafes flag incoherent score/justification pairs for human review.
- **Clean extraction.** PDFs are converted to markdown with images/graphics discarded and running headers/footers, page numbers, ligatures, and hyphenation removed before they reach the model.
- **Consistency & partial handling.** Cross-criterion consistency warnings, and explicit flagging when some criteria fail (renormalized, non-comparable score).
- **Cost & token accounting.** Token usage and an estimated USD cost are reported per document.

Reports are written as both **Markdown** (human review) and **JSON** (downstream processing).

## How it works

```
input/pdfs/*.pdf
   │  extract & clean (pymupdf4llm)
   ▼
clean text + per-page index
   │  8 criterion judges in parallel (litellm → OpenAI, forced function call)
   ▼
per-criterion verdicts  ──►  validation (grounding, coherence, page lookup)
   │  weighted aggregation + consistency check
   ▼
output/evaluations/<timestamp>.<name>_evaluation.{md,json}
```

See [`docs/architecture.puml`](docs/architecture.puml) (C4 component diagram) and [`docs/evaluation-flow.puml`](docs/evaluation-flow.puml) (runtime sequence) for the detailed design.

## Requirements

- Python **3.13**
- An OpenAI API key

## Setup

```bash
# 1. Create the environment (conda) and install dependencies
conda env create -f environment.yml
conda activate rigor
pip install -r requirements.txt

# 2. Create a .env file in the project root (required)
```

`.env` must define at least:

```dotenv
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini   # optional; default shown
```

## Usage

```bash
# Place the reports to evaluate in input/pdfs/, then run:
PYTHONPATH=libs python scripts/run_evaluation.py
```

Each PDF in `input/pdfs/` is evaluated and its reports are written to `output/evaluations/`.

## Configuration

All judge settings are read from the environment (sensible defaults shown):

| Variable                      | Default       | Description                                                                              |
|-------------------------------|---------------|------------------------------------------------------------------------------------------|
| `OPENAI_MODEL`                | `gpt-4o-mini` | Model used by every judge (any litellm-supported OpenAI model).                          |
| `EVALUATION_TEMPERATURE`      | `1.0`         | Sampling temperature. Leave **empty** for reasoning models that only accept the default. |
| `EVALUATION_SEED`             | `7`           | Seed for reproducible grading. Leave empty to omit.                                      |
| `EVALUATION_MAX_TOKENS`       | `8192`        | Max completion tokens per judge.                                                         |
| `EVALUATION_MAX_CONCURRENCY`  | `4`           | Concurrent judge calls (bounds provider rate limits).                                    |
| `EVALUATION_MAX_INPUT_TOKENS` | `100000`      | Soft limit; warns when a document may overflow the context window.                       |
| `EVALUATION_TIMEOUT_SECS`     | `180`         | Per-request timeout.                                                                     |
| `EVALUATION_MAX_RETRIES`      | `2`           | Retries on transient API errors.                                                         |

## Evaluation criteria

| Criterion                                          | Weight |
|----------------------------------------------------|--------|
| Contextualization of the organization and practice | 10%    |
| Problem and objectives                             | 15%    |
| Applied methodology                                | 15%    |
| Development and technical evidence                 | 25%    |
| Results obtained                                   | 15%    |
| Conclusions and reflection                         | 10%    |
| Writing, spelling and format                       | 5%     |
| Ethical use of AI                                  | 5%     |

The full rubric (level descriptors per criterion) is in [`criterios.md`](criterios.md).

## Project structure

```
libs/
  extraction.py        PDF → clean markdown (+ per-page index)
  evaluator/
    agents.py          criterion definitions & agent factory
    base_agent.py      CriterionAgent, JudgeConfig, LLM call
    prompts.py         shared preamble + 8 rubrics
    schemas.py         Pydantic output model → strict JSON schema
    scoring.py         level bands, 0.5-step snapping
    aggregation.py     weighted score, consistency checks
    validation.py      evidence grounding & coherence failsafes
    report.py          Markdown + JSON report generation
scripts/
  run_evaluation.py    batch CLI entry point
docs/                  C4 + sequence diagrams
```

## Credits

- [Mg. Diego Urrutia-Astorga](https://godie.cl), [Departamento de Ingeniería de Sistemas y Computación](https://www.disc.ucn.cl), [Universidad Católica del Norte](http://wwww.ucn.cl), Antofagasta, Chile.

## License

This project is open-sourced software licensed under the [Apache license](LICENSE).

---
&copy; 2026 Diego Urrutia-Astorga. All rights reserved.
