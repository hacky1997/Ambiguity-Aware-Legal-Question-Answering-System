# Tools and Technology

Companion to PROJECT_REQUIREMENTS v4. Read that first.

## How to read this

One rule, applied throughout: **every technology here traces to a numbered requirement. Anything that does not trace to one is in the rejected list, with the reason.**

That rule is the point. The failure mode for this kind of project is not picking a weak tool. It is picking eleven good ones, none of which is needed. Section 6 is therefore the most important section in this document.

A second rule for the model layer: **no embedding or reranking choice is final until it has been scored on your own corpus by your own harness.** Every source consulted while writing this says the same thing, and one reported that the top-ranked model on a public leaderboard was not the best on their own ten thousand document corpus once price was included. Public benchmarks tell you the shortlist. They do not tell you the answer.

---

## 1. What happens to the existing code

The current repository is roughly 5,600 lines. This is the disposition of every part of it.

### Keep and fix

| Part | What changes |
|---|---|
| `agent/` graph structure | The node factory pattern and typed state are sound. Rewire so the findings engine replaces `planner_node` and `policy_node`. Delete `route_from_policy`, which is a conditional edge with one destination. |
| `agent/state.py` | Move from `TypedDict` to a Pydantic model, so state is validated at every hop rather than only at the boundary. |
| `Interface/` FastAPI app | Keep. Fix the blocking call inside the async endpoint, which currently limits concurrency to one. Fix the request fields that are accepted, passed along, and never written into state. |
| `retrieve/retriever.py` BM25 | Keep the BM25 path. Section numbers and case citations are exact strings and dense retrieval handles them poorly. |
| `tests/` | Keep as a starting point. It currently tests file reading and nothing else that matters. |

### Replace

| Part | Replaced by | Why |
|---|---|---|
| Chroma `PersistentClient` | Qdrant | Single process on local disk, no replication, no snapshots, no payload filtering worth using. |
| `nlpaueb/legal-bert-base-uncased` | An embedding model chosen by your own eval | This is a masked language model checkpoint with no contrastive training. Using it for retrieval is almost certainly the largest silent quality loss in the current system. |
| Local Qwen generator | A hosted model API | Already your decision. Removes the Windows path in `config.py` that makes the Docker build unrunnable. |
| The three additive score boosts in the retriever | Normalise, then combine | RRF scores sit around 0.016 and the code adds a flat 0.35 for a regex match. The boost is twenty times the signal, so ranking is currently decided by regex and the embeddings are decorative. This is a correctness bug, not a tuning question. |
| `Experiments/` | `legalrag/evals.py` and `scripts/run_eval.py` | Spreadsheet reports are not a harness. Already written. |
| `requirements.txt` | `pyproject.toml` plus a uv lock file | Currently unpinned, with duplicate entries and mixed line endings. |

### Delete

| Part | Why |
|---|---|
| `GUI/` and PySimpleGUI | Dead alongside the FastAPI interface. |
| `memory/` | Wired into the CLI only and unreachable from the API. 448 lines of unreachable code. Conversation state belongs in the graph checkpointer if it is needed at all. |
| `ddgs` and BeautifulSoup web search | v4 turns external fetching off by default. It is the largest attack surface and is not needed for the system to work. Keep the switch, delete the implementation until the switch is turned on. |
| `config.py` hardcoded credential | Rotate the key first. Purge from history. Then delete. |
| `API_KEYS.txt`, `server.log`, `memory.db`, `vector_db/`, `.DS_Store` | Should never have been committed. |

---

## 2. Language and project tooling

Serves: delivery standards, and criterion 19 and 20.

| Need | Choice | Note |
|---|---|---|
| Language | Python 3.12 | 3.13 is fine. Do not chase 3.14 while parts of the ML stack lag. |
| Packaging and lock | **uv** | Fast, produces a real lock file, replaces pip, venv and pip-tools. The single biggest quality of life improvement over the current setup. |
| Lint and format | **ruff** | One tool replacing flake8, isort, black and more. |
| Types | **mypy** in strict mode, on `legalrag/` only | Strict everywhere is a tax. Strict on the findings engine and the extractors, where a wrong type is a wrong legal answer, is worth it. |
| Data models | **Pydantic v2** | Validation at every boundary, and it is what FastAPI uses anyway. |
| Tests | **pytest**, with **hypothesis** for the number parser | Property tests are the right tool for a word-to-number parser, and my own `1,00,000` bug is the argument. |
| Pre-commit | **pre-commit** | ruff, mypy, and the secret scanner, all before commit. |
| Secret scanning | **gitleaks** in CI, blocking merge | Criterion 19. Non negotiable given what is currently in the repository. |
| Dependency scanning | **pip-audit** or GitHub Dependabot | Criterion 20. |

---

## 3. The data layer

Serves: requirements 5.1 to 5.9.

| Need | Choice | Why this and not something else |
|---|---|---|
| Statute source | The published statute layer, structured endpoints | Requirement 5.1. Anonymous, CC BY 4.0. Attribution is a licence condition. Use the API, not the HTML. |
| Judgment corpus | The public S3 open data buckets | Requirement 5.8. No account needed, and the buckets are in the Mumbai region, which is fast from where you are. Read the parquet metadata and filter before pulling a single PDF. |
| Parsing and derivation | Plain Python, no framework | `punishment.py` and `materiality.py` are already written and tested. A rules engine library would add configuration syntax and remove the ability to unit test a function. |
| Vector store | **Qdrant** | Payload filtering gives you date and court filtering for free, plus snapshots, replication and quantization. Run it in Docker locally. |
| Alternative if you want one process | **Postgres with pgvector** | Legitimate if you already need Postgres for audit records. Slower at scale, one less service to run. Pick one, do not run both. |
| Keyword search | **BM25**, kept from the existing code | Exact strings matter more here than in most corpora. |
| Audit records | **Postgres** | Requirement 10, the recording clause. Not SQLite, which is single writer. |
| Migrations | **Alembic** | Because the audit schema will change and hand-editing tables is how data gets lost. |

---

## 4. The model layer

Serves: requirement 5.3 second reader, Section 9, and the generator.

### Embeddings

The current landscape, as of the checks made while writing this. Treat as a shortlist, not a decision.

| Option | Shape | Note |
|---|---|---|
| **Voyage 4 family** | Hosted API | `voyage-4` and `voyage-4-large` are reported as the strongest on pure retrieval quality. Check whether a current legal-domain variant exists; the older `voyage-law-2` was domain-tuned and a domain model is worth testing on a statutory corpus. |
| **Gemini embedding-001** | Hosted API | Reported as the strongest all-rounder. |
| **Cohere embed-v4** | Hosted API | Largest context window of the hosted options, competitive pricing, strong multilingual. Pairs with their reranker. |
| **OpenAI text-embedding-3-large truncated to 1024 dimensions** | Hosted API | Repeatedly called the value pick. Truncation cuts vector storage roughly threefold for a small quality drop. |
| **Qwen3-Embedding** or **BGE-M3** | Open weights | Top of the open leaderboards. Only cheaper than an API above roughly ten million embeddings a month, which you will not reach. Worth a run on Kaggle purely as a free baseline to compare against. |

**Method, and this matters more than the choice.** Shortlist two. Score both on your own corpus with your own harness. Record the result. Then commit, and record `embedding_model` and `embedding_version` in every chunk's payload and in the index name, because changing this later means a full re-index and you need to be able to run two indexes side by side to compare.

### Reranking

**Cohere Rerank 4.0**, or the Voyage reranker, or `Qwen3-Reranker` if self-hosting. A cheaper embedder plus a reranker frequently beats an expensive embedder alone and costs less overall. Budget for the reranker before upgrading the embedder.

### Generation and the second reader

Tiered, because the current graph makes up to seven model calls per question and points all of them at the same model.

| Role | Tier |
|---|---|
| Final answer generation | Frontier tier. The only place quality is visible. |
| Relevance check, query rewrite | Cheap and fast tier. Binary and rewrite tasks. |
| Second reader for materiality (Section 9) | **Must be a different provider from the generator.** Same family means correlated failure, which defeats the entire purpose. |
| Behaviour decision | **No model at all.** The findings engine is deterministic. |

Access through a single thin adapter of your own, not a framework abstraction, so the provider is one line to change and the harness can record exactly which model version produced a run.

---

## 5. The application layer

| Need | Choice | Serves |
|---|---|---|
| Graph orchestration | **LangGraph** | Already in use. Still the right fit for typed state, conditional routing and auditability. **Pin the version hard.** The API has churned: the interrupt primitive has moved more than once and checkpoint formats have broken across minor versions. Pin, and read the changelog before upgrading. |
| API | **FastAPI** | Already in use. Fix the blocking call in the async path. |
| Async model calls | **httpx** with explicit timeouts | Requirement 11. |
| Observability | **OpenTelemetry**, GenAI semantic conventions | Vendor neutral. Export wherever you like. |
| Trace viewer | **Langfuse** self-hosted, or **LangSmith** | Langfuse if you want it free and in your own Docker compose. LangSmith is a paid add-on. |
| Retries and circuit breaking | **tenacity** plus a small breaker | Requirement 11. Do not pull in a service mesh for this. |
| Containers | **Docker**, multi stage, non root, with a healthcheck | Current Dockerfile runs as root, has no healthcheck, and cannot start because of a hardcoded Windows model path. |
| CI | **GitHub Actions** | ruff, mypy, pytest, gitleaks, pip-audit, then the eval gate. |

### Guardrails

Requirement 10. Note carefully what is bought and what is written.

| Guardrail | Approach |
|---|---|
| Injection detection | A library is reasonable here. **NVIDIA NeMo Guardrails** or **Guardrails AI**. Do not hand roll a classifier. |
| Personal data detection | **Microsoft Presidio**. Solved problem, well tested. |
| Grounding verification | **Write it yourself.** Requirement 5.2 gives every passage a stable identifier, the generator cites by identifier, and verification becomes a join rather than fuzzy text matching. No library does this against your identifier scheme. |
| Citation and repeal checks | **Write them yourself.** Both are lookups against your own data. These are the two hard guarantees in v4 and they must not depend on a third party. |
| Advice boundary and scope | **Write them yourself.** Domain specific. |

---

## 6. Rejected, with reasons

The important section.

| Rejected | Why |
|---|---|
| **Knowledge graph, Neo4j, GraphRAG** | The in-force question is a table with a handful of rows. Citation traversal is a nice-to-have. Neither justifies a graph database, an ontology, or a second query language. Cut in v3 and staying cut. |
| **Published MCP servers** | v4 cut the integration surface. There is nothing to integrate with yet. MCP is likely to be the standard for agent-to-tool communication and is now under neutral governance, so this is a later decision, not a never decision. |
| **Multi-tenant access control** | One public corpus. No organisations. This was pure decoration in v3. |
| **A second agent framework** | CrewAI, AutoGen, OpenAI Agents SDK, Microsoft Agent Framework are all credible. None solves a problem LangGraph is failing to solve here. Switching costs a rewrite and buys nothing. |
| **A learned ambiguity model** | Requirement 7.5 gates this behind the residual study. The likely outcome of that study is that nothing gets built, and that is a success. |
| **Redis or a cache layer** | You have no traffic. Add when you have measured a latency problem. |
| **Kubernetes** | One container. Docker Compose. |
| **A feature store, a model registry, an experiment tracker** | You are not training a model. |
| **Fine tuning anything** | The findings engine is deterministic and the generator is an API. There is nothing to fine tune. |
| **A memory or note-taking subsystem** | The original repository already had one that was unreachable from the API. Building a second one repeats the exact mistake. Conversations here are three turns. |
| **Context compaction** | Nothing to compact. |
| **Streaming responses** | Tempting. Conflicts with output guardrails, because you cannot ungrounded-check text you have already sent. Add only after grounding verification works, and only by buffering to the guardrail boundary. |

---

## 7. Version discipline

Three things bite, in order of likelihood.

**LangGraph.** Pin exactly. State channel semantics and checkpoint formats have changed in ways release notes call minor and users call breaking.

**Embedding model.** Changing it means a full re-index. Version the index name, record the model in every payload, keep the ability to run two side by side.

**Model API versions.** Pin the model string, never an alias that silently moves. Record the exact string in every evaluation report, or your baseline comparison is meaningless because the baseline was produced by a different model.

---

## 8. Repository layout

```
pyproject.toml            uv, ruff, mypy, pytest config in one file
uv.lock
legalrag/
  config.py               Pydantic settings, from environment, no secrets in code
  punishment.py           written and tested
  materiality.py          written and tested
  evals.py                written and tested
  identify.py             next: provision identification
  findings.py             next: F1 to F14 and combination
  retrieval.py            Qdrant, BM25, normalise then fuse, rerank
  generate.py             branch-scoped generation
  guardrails/             one module per guard, each independently testable
  llm.py                  thin provider adapter
  telemetry.py            OpenTelemetry setup
agent/                    LangGraph wiring, existing, rewired
api/                      FastAPI, existing, fixed
scripts/
  fetch_corpus.py         written
  build_correspondence.py written, one seam left open
  run_eval.py             written
  derive_thresholds.py    next: requirement 5.4
data/
  sources.yaml            written
  correspondence.jsonl    generated
  adjudication_queue.jsonl generated
  golden.jsonl            hand and derived, with label_source on every row
  baseline.json           generated
tests/
docker/
```

---

## 9. Where to start writing code

In this order, and the order matters because each step makes the next one testable.

1. **Rotate the credential, purge history, add gitleaks to CI.** Nothing else until this is done.
2. **`pyproject.toml`, uv lock, ruff, mypy, pre-commit, CI skeleton.** One afternoon, and every later step is easier for it.
3. **Wire `fetch_pair` in `build_correspondence.py`** to the structured statute endpoints. Confirm the response field names against the publisher's API documentation. Cache to disk on the first run so you are not refetching a public source to debug a regular expression.
4. **Run the correspondence build over the full old code.** Read the adjudication queue. Its size and its causes tell you more about this project than any design document, including this one.
5. **`derive_thresholds.py`.** Requirement 5.4. The split threshold comes from the score-gap distribution, and until it does the document and the build contradict each other.
6. **`identify.py`.** Every finding depends on it. Nothing downstream is testable without it.
7. **`findings.py`.** F1 to F14 and combination. Pure functions over identification output and the correspondence file. No model calls, no input or output, fully unit testable.
8. **Golden set, then the model baseline.** Label source on every row. Lead with the label-free comparison: determinism under repeated runs, evidence verification rate, abstention stability under rephrasing, cost, latency. Accuracy comes second, partitioned by label source, with circular partitions marked as circular in the report.
9. **Retrieval, rebuilt.** Qdrant, the passage granularity in requirement 5.2, normalise before combining scores, reranker.
10. **Generation and guardrails.** Branch-scoped generation, then grounding verification against passage identifiers, then the rest.

Steps 6 and 7 are the project. Everything before them is preparation and everything after them is delivery.
