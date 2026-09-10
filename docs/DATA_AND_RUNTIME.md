# Data and Runtime

Companion to PROJECT_REQUIREMENTS v4 and TOOLS_AND_TECH.

---

## 1. First, the premise

**You are probably not training anything.**

Requirement 7.5 gates any learned component behind the residual study, and the expected outcome of that study is that nothing gets built. The findings engine is deterministic. The extractors are regular expressions. The generator is an API. There is no model in this project that has weights you own.

So "we need somewhere to keep training data" is answering a question you do not currently have. Scenario C below covers the case where the residual study says otherwise, and it is deliberately last, because treating it as the default shapes every other decision wrongly.

Hugging Face still earns a place, for different reasons. Section 3.

---

## 2. What data actually exists

Sizes assume the first library: roughly five thousand filtered judgments plus the six acts.

| Data | Size | Rebuildable | Lives where |
|---|---|---|---|
| Source statutes | a few MB | Yes, refetch | Not stored. Fetched and cached. |
| Source judgments, raw PDFs | 2 to 5 GB | Yes, refetch | Local cache only. Never committed. |
| Extracted text | ~500 MB | Yes, from PDFs | Local cache. |
| Passages, chunked | ~250k records | Yes, from text | Local cache, then indexed. |
| Vector index | ~1.5 to 2 GB | Yes, re-embed | Qdrant volume. Never in git. |
| `correspondence.jsonl` | ~1 MB, ~553 rows | Yes, from sources | **Git.** |
| `adjudication_queue.jsonl` | small | Yes | Git, generated. |
| **Adjudication dispositions** | tiny | **No** | **Git. This is the one irreplaceable thing.** |
| `vocabulary.json`, `in_force.json` | small | Yes | Git. |
| `thresholds.json` | tiny | Yes, from distribution | Git, with the distribution it came from. |
| `golden.jsonl` | small, few hundred rows | Partly | **Git.** Hand-checked rows are not rebuildable. |
| `baseline.json` | tiny | Yes, by rerunning | Git. |
| Eval reports | small each | Yes | CI artifacts. |
| Audit records | grows with traffic | No | Postgres. |

### The rule that follows

**Two things in this entire project cannot be regenerated: the adjudication dispositions and the hand-checked golden rows.** Both are small enough to sit in git and both represent human decisions.

Everything else is a cache. The vector index is two gigabytes and it is worthless, because you can rebuild it from public sources in an hour. Do not back it up. Do not put it in git. Do not treat losing it as an incident.

Getting this wrong in either direction is expensive. People back up the two gigabyte index and lose the one megabyte file that took real thought.

---

## 3. Does Hugging Face earn a place

Not as a training store, because there is nothing to train.

**Two honest uses.**

**Versioned publication of the derived artifacts.** The correspondence file, the vocabulary, the golden set. HF Datasets gives you versioning, a public URL, and a dataset card that documents provenance. For a project whose central claim is "I derived this data by code from published sources, here is exactly how", a citable artifact is worth more than the code that made it.

Honest caveat: git-lfs or an S3 bucket does the same job. HF adds discoverability and a card format, not capability. Do not pretend it is infrastructure.

**One thing to think about before publishing the golden set.** Making it public makes it a benchmark, which is good for credibility. It also means it can appear in future training data, which is the standard contamination problem. It does not affect you now, because you train nothing. Note it in the card and move on.

**Where HF becomes real infrastructure:** only under Scenario C.

---

## 4. Scenario A. Laptop

The mode you will actually be in almost all of the time.

**Shape.** Everything on one machine. Docker Compose for the two services that need to be processes. No cloud beyond model API calls.

```
docker compose up
  qdrant     :6333    volume ./data/qdrant
  postgres   :5432    volume ./data/pg
uvicorn api.main:app  :8000
```

**End to end.**

1. `uv sync` and the environment exists, pinned.
2. `scripts/fetch_corpus.py --tier core` pulls the parquet metadata first, filters to criminal matters citing the penal codes, then pulls only those PDFs. Cached under `data/raw`, which is gitignored.
3. `scripts/build_correspondence.py` fetches provisions from the statute API, runs the sentencing extractor, writes `correspondence.jsonl` and `adjudication_queue.jsonl`. Both committed.
4. You work through the queue. Dispositions committed. **This is the only irreplaceable work in the project.**
5. `scripts/derive_thresholds.py` computes the split threshold from the score-gap distribution and records it with the distribution.
6. Chunk to the granularity in requirement 5.2. Embed through the API. Roughly 250k passages at around 300 tokens each is about 75 million tokens, so **somewhere between two and ten dollars** depending on which model you pick. Once. Index into Qdrant.
7. `uvicorn` and ask it questions.
8. `scripts/run_eval.py --baseline data/baseline.json` before every commit that touches the findings engine.

**Cost.** Embeddings once, under ten dollars. Then per-question model calls only. Development is effectively free.

**What breaks.** You delete the Qdrant volume, and you rebuild it in an hour. You lose your laptop, and everything that mattered was in git.

**This is the demo mode.** Docker Compose up, ask it the section 302 question, show it returning both codes. That is the whole demo and it runs on a laptop with no cloud account.

---

## 5. Scenario B. Deployed for real users

Only when someone other than you will use it.

**Shape.** Small. Resisting the urge to make this diagram bigger is most of the work.

```
Container            API, non root, healthcheck
Qdrant               managed, or a container with a real volume and snapshots
Postgres             managed, for audit records
Object storage       nightly Postgres dumps, and the passage cache
Model APIs           generation, cheap tier, embeddings, rerank
CI                   GitHub Actions
Traces               Langfuse, self hosted alongside, or LangSmith
```

**End to end.**

1. Steps 1 through 6 of Scenario A run in CI, not on your laptop, and produce the index as a build artifact.
2. **The index is built and versioned, never mutated in place.** `chunks_v3_<model>_<date>`. Deploy points at a name. Rolling back retrieval is repointing a name.
3. CI runs ruff, mypy, pytest, gitleaks, pip-audit, then the eval gate. A regression in unsafe confidence exits non-zero and the build fails.
4. Container deploys. Health check reports genuine readiness, meaning the index is reachable and the model API answered, not merely that the process started.
5. Every request writes an audit record to Postgres and a trace to the collector.
6. Alerts on error rate, latency, cost, guardrail false positive rate, and any sudden shift in behaviour distribution. That last one is the interesting alarm: if the proportion of questions getting the ask behaviour jumps overnight, something upstream broke, probably identification.

**Cost.** Small instance, managed Postgres, Qdrant either managed or on the same box. **Tens of dollars a month plus per-question model calls.** The model calls dominate once there is traffic, which is the argument for the tiered model assignment in the tools document rather than pointing all seven calls at the frontier tier.

**Backups.** Postgres nightly. The two irreplaceable files are in git and therefore already backed up. Nothing else.

**What breaks.** Model API outage, so the circuit breaker opens and the system degrades to saying it cannot answer rather than hanging. Qdrant volume lost, so you rebuild from the CI artifact. Bad deploy, so you repoint the index name and redeploy the previous container.

---

## 6. Scenario C. The training branch

**Entered only if the residual study says the residual is large and structured.** If it does not, this scenario never happens and that is the good outcome.

Even then, the thing being trained is small: a classifier over identification output, not a language model.

**Shape.**

```
Kaggle notebook, GPU     training
Kaggle Dataset           corpus, attached read only at /kaggle/input
HF Hub, private repo     checkpoints and the final model
/kaggle/working          scratch, ~20 GB, survives commit only
Local or Scenario B      inference, model pulled from HF
```

**End to end.**

1. Package the training data as a Kaggle Dataset and attach it read only. Do not download it per session.
2. Notebook settings: GPU on, internet on, which needs phone verification or Hugging Face downloads fail.
3. Train. **Checkpoint to `/kaggle/working` every N steps, then push to the private HF repo.** Sessions cap around twelve hours and die without warning, so a run that only checkpoints at the end is a run you will lose.
4. Final model pushed to HF with a tag. The tag is recorded in the config and appears in every evaluation report.
5. Inference pulls by tag. Never by branch name, because a moving reference means your baseline was produced by a different model than the one being tested and the comparison is meaningless.
6. The eval gate is unchanged. The learned component competes against the deterministic one on the same golden set, using the same harness. **If it does not beat the rules, it does not ship.**

**Quota.** Roughly thirty GPU hours a week, subject to change, so check current limits. A small classifier trains in under two hours, which fits comfortably.

**Cost.** Free. That is the point of using Kaggle rather than renting a GPU.

**What breaks.** Session dies mid run, and you resume from the last HF checkpoint. Quota exhausted, and you wait. Model underperforms the rules, and you delete it, which is a successful outcome of the study and not a failure.

---

## 7. Choosing

| | A. Laptop | B. Deployed | C. Training |
|---|---|---|---|
| When | Always | Real users | Only if the residual study fires |
| Cloud account needed | No | Yes | Kaggle and HF, both free |
| Cost | Under ten dollars once | Tens per month plus calls | Free |
| Is HF needed | No, optional for publication | No | **Yes, this is the one** |
| What you lose if it dies | Nothing in git survives loss | Nothing, rebuild from CI | The current run |

**Start in A and stay there until someone else needs access.** A working laptop deployment that answers the section 302 question correctly, with an evaluation harness and a passing CI gate, is a stronger thing to show than a cloud deployment with an empty index.

---

## 8. The two files to be careful with

Everything in this document reduces to this.

`data/adjudication_dispositions.jsonl` and the hand-checked rows in `data/golden.jsonl` are the only artifacts in the project that represent judgement rather than computation. They are small, they are in git, and they are the reason the project is defensible.

The two gigabyte vector index is not important. Losing it costs an hour and a few dollars.

Back up the small file. Not the big one.
