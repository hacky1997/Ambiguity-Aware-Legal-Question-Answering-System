# legalrag

Ambiguity-aware question answering over Indian criminal law.

When a legal question can be read more than one way, most systems pick a
reading and answer with full confidence. The user never learns a choice was
made. This one decides between four responses instead: answer, answer with a
stated assumption, ask one targeted question, or show the alternatives.

The decision is made by rules, not by a model. Same question, same answer,
same recorded reasons, every time.

## Governing principle

The system asserts text facts and never legal conclusions. Every claim carries
the exact substring it came from, verified against the source. Where a legal
conclusion would be needed, both texts are shown and the reader decides.

A system that makes no legal claims requires no legal validation.

## Documentation

- `docs/REQUIREMENTS.md` what is being built and what finished looks like
- `docs/DECISIONS.md` every reversal, with the reasoning and what would change it back
- `docs/DISCOVERIES.md` what was learned by checking rather than by thinking
- `docs/TOOLS_AND_TECH.md` technology choices, each traced to a requirement
- `docs/DATA_AND_RUNTIME.md` where data lives and how this runs

## Status

| Component | State |
|---|---|
| Sentencing extractor | done, tested |
| Materiality comparison | done, tested |
| Provision identification | done, tested |
| Findings engine, F1 to F16 | done, tested |
| Evaluation harness | done, tested |
| Correspondence builder | one seam open, needs the source wired |
| Retrieval, generation, guardrails, API | not started |

## Attribution

Statutory text and computed cross-code mappings come from IndiaCode by
eCourtsIndia under CC BY 4.0. Attribution is a licence condition, not a
courtesy. Judgments come from public open data under CC BY 4.0.

Correspondence between the two eras of the criminal codes is **computed by text
comparison and is not official**. No government machine-readable mapping exists.

## Develop

```
uv sync --all-extras
uv run pytest
uv run ruff check legalrag tests scripts
```
