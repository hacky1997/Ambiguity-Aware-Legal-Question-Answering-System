# Delivery Plan for the Ambiguity-Aware Legal Question Answering System

## 0. Purpose

This is the build plan for finishing the 5.0 version of the project. The project already contains the hardest part of the design: a deterministic rule engine that decides when to answer, ask, or show alternatives without pretending to be a legal authority.

That is the right shape. The remaining work is not to invent new doctrine. It is to connect the rules to data, make the system runnable, and make the output safe enough that a person can trust the warning labels rather than the wording.

This document is intentionally narrow. It does not describe a second architecture, a learned shortcut, or a broad platform. It describes the work that must be completed in order for the project to leave the design phase and become a running system.

---

## 1. Current state

The core logic is already present and it is the project’s strongest asset.

- `legalrag/models.py` defines the shared values: code, provision references, candidate confidence, findings, and behaviour.
- `legalrag/identify.py` handles explicit citations, bare numbers, vocabulary lookup, heading match, date resolution, and candidate ordering.
- `legalrag/punishment.py` extracts sentencing signals from statutory text and keeps every value tied to a verified span.
- `legalrag/materiality.py` compares two provisions by sentencing fields rather than similarity score.
- `legalrag/findings.py` collects every applicable rule, computes the most cautious behaviour, and reports each contributing finding.
- `legalrag/evals.py` implements the deterministic evaluation harness, per-finding reporting, and the release gate.

That is a substantial fraction of the product and it is where the dangerous logic lives. The rules are already built to be careful where care is required.

The remaining scope is therefore operational and infrastructural rather than conceptual:

- package and environment stability
- ingestion and versioned data build
- correspondence and adjudication queue
- retrieval and evidence flow
- response assembly
- guardrails and audit records
- deployment and monitoring

---

## 2. Phase 1: stabilise the build

The first job is to make the project run as a package in a normal Python environment, not only by manually adding the repository root to `PYTHONPATH`.

### 2.1 Package import fix

The current failure is not a rule failure. It is a packaging failure: the project imports as a namespace package in some environments and as a missing package in others. The project must be installable via the declared toolchain and the test command must be reproducible from a clean environment.

Required work:

- confirm the project installs cleanly with the project’s configured dependency flow
- ensure `legalrag` resolves as a real package under the supported interpreter
- verify the import path from a clean checkout, not only from the current editor session
- ensure CI and local development use the same command path

### 2.2 Lock and toolchain agreement

The project already declares `uv` usage in the repository docs. The lock file exists, and the toolchain version must be fixed before the real work proceeds.

Required work:

- run `uv sync --all-extras`
- run `uv run pytest`
- run `uv run ruff check legalrag tests scripts`
- keep the package install path and the test path identical across local and CI usage

### 2.3 Release gate and contract freeze

The harness is the release gate. It is deterministic, records the system under test, and reports the rate that matters without pretending it is a generic accuracy number.

This means the next work is constrained by the harness rather than by intuition. The project must not add new answer-generation logic before the evaluation contract is stable under a clean run.

---

## 3. Phase 2: ingestion and dataset build

This is the first true delivery layer. Without it, the system has rules but no data and no library.

### 3.1 Statutes

The statutes are the simplest part of the data layer and are not where the risk sits.

Required work:

- enumerate every section from the published section index
- fetch each provision from the structured statute endpoint, not the HTML layer
- cache on first fetch to disk
- store act, section, sub-section, heading, text, commencement and cessation
- attach attribution required by the licence
- maintain a clean separation between the cache and the code path that reads it

The build requirement is not whether the fetch works once. It is whether the fetch can be re-run safely, with the same sections and the same output, without refetching a public source during debugging.

### 3.2 Judgments

This is the risk path and it must be designed carefully. It is neither small nor simple, and it cannot be left as “some retrieval later.”

Required work:

- store every judgment with extraction method and quality score
- exclude documents below the threshold rather than indexing bad text silently
- count and report excluded documents and duplicate documents
- detect paragraph numbering with a pattern rule and fallback to structural chunking when numbering is absent
- extract provision references in old and new numbering, formal and abbreviated forms
- carry citation data into the passage metadata and vocabulary
- deduplicate on case identifier, court and date, preferring the richest extraction
- re-run ingestion safely without rebuilding everything from scratch

The rule here is simple: a silently garbled judgment must never produce a confident citation to nonsense.

### 3.3 Versioned index build

Indexing is a build artifact, not an in-place mutation.

Required work:

- build the chunk index as a versioned artifact
- name it using the required pattern: `chunks_v{n}_{embedding_model}_{date}`
- publish a deployment pointer to a concrete version
- make rollback a matter of repointing the name, not rebuilding the world
- keep two versions side by side for comparison when needed

This sharply reduces the operational risk in retrieval and makes the state of the system measurable.

---

## 4. Phase 3: correspondence, materiality, and adjudication queue

This is the point at which the project stops being “a rules engine” and becomes “a legal evidence system.”

### 4.1 Correspondence file

The project already states that there is no official government mapping. The correct approach is therefore to derive the correspondence file from public sources and treat it as a working reference, not as law.

Required work:

- compute closest provision by similarity
- record ranked alternates
- record explicit no-close-match cases
- record split and merged candidates
- record disputed rows
- mark every row as either settled or queued

The key question is not whether the mapping is pretty. It is whether the mapping is auditable, explained, and traceable back to a computed source.

### 4.2 Adjudication queue

The queue exists because disagreement is a product state, not a bug.

Required work:

- if a row sits in the queue and is not dispositioned, it defaults to disputed
- route misplaced or unresolved rows to alternatives behaviour
- report the proportion of queued provisions as a system health metric
- ensure the queue is not silently ignored

This matters because the product degrades from answering to hedging when the queue grows.

### 4.3 Materiality comparison

The project already has the right signal design: similarity answers “which provision is the likely counterpart,” while sentencing extraction answers “did the punishment change.” These are independent signals and they must both be present.

Required work:

- compare sentencing values on all relevant fields
- treat any difference in any field as material
- keep span verification as a hard requirement
- report parse rate, partial-parse rate, and unparsed provisions separately
- drive the adjudication queue whenever the signals disagree

This is a crucial design decision. It is the place where the project stops making legal assumptions and starts making text-based comparisons that are checkable by a reader.

---

## 5. Phase 4: retrieval

Retrieval is not a general search problem. It is a narrow operation over a library of judgments and a small set of residual search cases.

### 5.1 Statutes never go through retrieval

This is a major design decision and it must remain intact.

Required work:

- resolve the provision identifier first
- fetch the statute by key, not by search
- reject any path that lets a search override a named provision
- test this directly in the project harness

This is the single most important anti-corruption measure in the system.

### 5.2 Judgment retrieval: dual-list search

Judgment retrieval must run two searches in parallel and combine them by score, not by a flat bump.

Required work:

- perform a meaning search over the judgment corpus
- perform a word search over the judgment corpus
- rank each list independently
- combine them by score weighting, with a tuned setting recorded in the build artifact
- never add a flat amount to a score
- keep the weights visible and measured
- apply filtering at the store before search: provision, court, and date where the conversation has established them

This is where earlier versions failed badly. The failed design added a constant to search scores so that pattern matches dominated the rankings and the meaning search had no practical effect. That is not a tactical mistake. It is a design error and it must not be repeated.

### 5.3 Reordering pass

The final ordering comes from a second, more accurate pass.

Required work:

- shortlist the top candidates from the combined search
- re-read each candidate against the question
- reorder the shortlist based on question fit and candidate quality
- keep the combining step narrow and deterministic
- keep the reordering step as the place where real effort is spent

This is the correct boundary: the combine step fetches the shortlist; the reorder step decides the final order.

### 5.4 Caching

Determinism is not optional here.

Required work:

- cache the deterministic prefix based on the normalised question and the data version
- key the cache on the versioned correspondence file, vocabulary and thresholds
- make repeat questions cost nothing rather than invoking a model call
- invalidate on data updates rather than on a vague “something changed” principle

This turns repeated questions into a tiny cost and makes the system easier to evaluate.

---

## 6. Phase 5: response assembly and the interactive contract

The response layer is the visible product. It must be built to the same standard as the rules.

### 6.1 Response schema

Each response must carry:

- behaviour
- findings, with their reason in plain words
- assumption, when the behaviour is answer-with-assumption
- content shaped by the behaviour
- citations with passage identifier, act, section, sub-section, case paragraph where relevant, in-force dates and quoted span
- data provenance and licence attribution
- coverage note where relevant
- advice notice
- bound facts in effect at the time of the response

The response is not just a result string. It is a traceable record of what the system decided and why.

### 6.2 Behaviour ordering and alternative rule

Alternatives must not imply a legal conclusion. They are ordered by a stated rule, and the rule must be explicit in the response.

The current design says alternatives are ordered by the commencement date of the governing act, and that rule is recorded in the answer.

Required work:

- enforce the ordering rule in the response layer
- state the rule plainly in the rendered output
- keep alternative ordering stable and reproducible

### 6.3 Conversation and resume

The interactive flow matters because legal questions often fail because the missing fact is small but crucial.

Required work:

- carry bound facts: date, court, offence identity, and code
- bind the fact at the turn it was obtained
- treat the date bound on turn two as a date given on turn three
- re-run identification and findings with all bound facts present
- when a follow-up reply answers the previous ask, re-answer the original question rather than restating it
- when a follow-up changes the subject, discard the pending ask and treat the new question as a fresh turn
- when the user says they do not know, fall back to alternatives rather than refusing or guessing
- ask at most twice for the same fact before falling back to a useful alternative response

This is where the product becomes usable rather than merely correct in the abstract.

---

## 7. Phase 6: guardrails, audit records, and safety

The system is not allowed to be clever at the cost of being dangerous.

### 7.1 Inbound guardrails

Required work:

- detect instruction manipulation and block it with logging
- strip personal data before processing or logging where possible
- confirm the subject area before trusting the request context
- reject personal advice and out-of-area requests at the boundary
- route blocked requests to a review queue rather than silently refusing

### 7.2 Outbound guardrails

Required work:

- check personal data before sending anything to an external service
- attach the advice notice to every response
- keep behaviour, findings and assumptions plainly visible
- ensure the system fails closed, not open
- measure false positive rate per guardrail and treat a high rate as a defect

### 7.3 Grounding verification

This is a hard requirement and it is not optional.

Required work:

- every cited provision must exist
- every quoted span must match the source text
- every repealed provision must be labelled as repealed with the relevant date
- keep verification mechanical and bounded to identifier joins where possible
- only use a model call for claims that cannot be matched by identifier

This is the safety boundary between “helpful” and “pretending certainty.”

### 7.4 Audit records

Every request must produce an audit record.

Required work:

- keep the question after personal data removal
- record candidates and confidence
- record bound facts and the turn they were bound
- record all findings and the behaviour chosen
- record assumption, guardrails and sources
- record component versions and index version
- record time and cost

A system that cannot explain the decision is not a safety system. It is a black box.

---

## 8. Phase 7: deployment, performance, and operational readiness

This is the operational mode that makes the project worth running.

### 8.1 Performance budget

The project already says the model-call budget is tight and the target is explicit.

Required work:

- keep behaviour decision at zero model calls
- allow generation to happen once
- allow retrieval relevance checks and rewrite steps only at the retrieval path
- keep grounding to identifier joins unless a model call is unavoidable
- measure total calls per question and alert above budget

### 8.2 Response-time and cost budget

Required work:

- set the target before launch
- measure the slowest one in twenty, not only the average
- alert when the target is missed
- track cost continuously by question and by caller
- cut off automatically when the per-caller or overall limit is reached

### 8.3 Health check and rollback

Required work:

- deploy based on a versioned index name
- report genuine readiness, not only process liveness
- make rollback a matter of pointer change rather than a rebuild
- alert on sudden shifts in the mix of response types

This is not a luxury. It keeps the product honest.

---

## 9. Phase 8: evaluation and release gate

The evaluation harness is the real product measure and it must be used continuously.

### 9.1 Per-finding floor

The project requires coverage per finding and the harness reports any finding below the minimum threshold.

Required work:

- build the golden set to at least twenty items per realistic finding
- keep coverage per finding as a release gate, not as an optional ambition
- measure unsafe confidence separately from overall correctness
- measure unnecessary asking separately from overall correctness
- measure wrong-and-confident identification separately

### 9.2 Baseline and model baseline

Required work:

- run a frontier model with the same retrieval path
- compare against the same golden set
- report label-free comparisons first
- keep model comparisons clearly separated from label-source analysis
- mark circular partitions in the report itself

This exists to stop the project from mistaking “the model agrees with itself” for “the system is correct.”

### 9.3 Regression exit

The gate is asymmetric by design.

Required work:

- unsafe confidence and wrong-and-confident must have zero tolerance
- other cases may permit small movement, but only by explicit action
- update the baseline only by an explicit action, not by accident
- every CI run must exit non-zero on regression

---

## 10. Execution order

The work must not be done in arbitrary order. The dependencies are explicit.

1. fix package import and environment stability
2. get the deterministic rule layer passing under a clean project run
3. build the ingestion pipeline for statutes and judgments
4. build the versioned index and provenance model
5. compute the correspondence file and adjudication queue
6. implement retrieval for judgments and direct statute lookup
7. implement response schema and conversation flow
8. add guardrails and audit records
9. implement operational metrics, budget alerts and health checks
10. run the golden-set gate and release only when thresholds and findings coverage are satisfied

This order is not a suggestion. It is the minimum safe order for a project in which the risk is not only an incorrect answer but a confident wrong answer.

---

## 11. The practical conclusion

The project already contains the most important design work. The rules are in place, the safety posture is in place, and the evaluation harness is in place. The remaining tasks are not “new invention.” They are the work of turning the design into a working system.

The missing steps are therefore straightforward in structure but not in importance:

- install and run the package correctly
- ingest the data without silent corruption
- compute and queue the correspondences
- retrieve judgments safely without letting search override a named provision
- render responses in a bounded, grounded schema
- protect the system with guardrails, audits and operational checks

That is the remaining work. It is sizeable, but it is not unfocused. It is the final layer between the rules and a system that can be trusted to answer carefully.
