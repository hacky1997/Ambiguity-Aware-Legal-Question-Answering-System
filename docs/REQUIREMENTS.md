# Project Requirements Specification

## Ambiguity-Aware Legal Question Answering System

Version 5.0. Supersedes 1.0 through 4.0.

---

## 0. Change Record

### Earlier versions

**1.0** claimed an official government mapping existed; it does not. Put a learned mechanism at the centre with legal rules as exceptions, which was backwards. Demanded an offence date before answering anything.

**2.0** used first-match-wins on the rules, discarding findings. Let the date rule fire ahead of the disputed-correspondence check. Gave provision identification one sentence. Required record-level deletion from backups, which is not achievable.

**3.0** assumed correspondence and materiality had to be produced by hand. They do not.

**4.0** cut the scope back from multi-tenancy, five integration capabilities, domain packs and a compliance programme. Added the text-facts-only principle. Specified the evaluation harness.

### What 5.0 adds

Two mechanisms that 4.0 named without designing, and thirteen gaps found by walking a request end to end as an implementer rather than reading the document as a reviewer.

**Designed properly.** Retrieval, Section 8. Conversation and resume, Section 9. Both were single sentences in 4.0, which is the failure mode where a document looks complete and is not.

**New sections.** Response schema, Section 10. Ingestion, Section 6. Both were entirely absent.

**Fixed.** Statutes no longer go through retrieval at all. Golden set sizing is now quantified and it changes the plan. Acceptance criteria are split by operating scenario. Cost and latency have budgets. Determinism is used for caching. Grounding verification is bounded. A default disposition exists for an unworked adjudication queue.

**Added.** Findings F15 and F16, for procedure-versus-substance and for multi-provision questions. Both were reachable through the scenarios in earlier versions and had no rule.

---

## 1. Purpose

What is being built, why, and what finished looks like. No project dates.

---

## 2. The Problem

Question answering systems pick a reading and answer with full confidence when a question can be read more than one way. The user never learns a choice was made for them.

This matters more in law than elsewhere. The answer is often a section number or a sentence length, so it arrives looking precise. The user usually cannot check. And a wrong answer is formatted identically to a right one.

**The situation.** India replaced the Indian Penal Code of 1860 with the Bharatiya Nyaya Sanhita, 2023, the Code of Criminal Procedure, 1973 with the Bharatiya Nagarik Suraksha Sanhita, 2023, and the Indian Evidence Act, 1872 with the Bharatiya Sakshya Adhiniyam, 2023. All three came into force on 1 July 2024.

The old codes still govern. Which law applies turns on when the offence was committed, not when the case was filed. Both bodies are live and will remain so for years. Numbering was reorganised rather than adjusted, so nothing carried across at the same number and several familiar old numbers now mean something entirely different. Separately, High Courts differ on many points with the matter unsettled.

**The scenarios.** Which law applies: carried across unchanged with no date given; materially changed with no date given; dates either side of the changeover; material with no date sensitivity; questions mixing the offence with the procedure. Which provision is meant: a bare number valid in both codes; old numbers used from habit; everyday words mapping to several offences; punishment questions naming no offence; language mapping to nothing; questions naming two provisions at once. More than one answer correct: split provisions; merged provisions; disputed correspondence; open court disagreements; no successor; new offences. Cannot be answered: not in the library; near-miss retrieval; false premise. Should not be answered: personal advice; out of area; manipulation.

Every one is the same situation. Something needed for a single correct answer is missing, contested, or genuinely plural, and a conventional system resolves it invisibly.

---

## 3. What The System Does

Four responses.

**Answer.** One clear reading, with sources.

**Answer with a stated assumption.** Answers, states the assumption at the top, says what changes if it is wrong.

**Ask.** One short targeted question for the missing fact.

**Show the alternatives.** Each presented with the conditions under which it applies.

### 3.1 Governing principle: text facts only

**The system asserts text facts. It never asserts legal conclusions.**

A text fact is checkable by anyone who can read, and the system quotes the span so they can. "The maximum fine in the old provision is 250 rupees; in the new provision it is 10,000" is a text fact.

A legal conclusion requires standing the system does not have. "The new provision is the legal equivalent of the old one" is a legal conclusion.

Where a legal conclusion would be needed, the system shows both texts, states the correspondence is computed by text comparison and is not official, and lets the reader decide.

This is what makes the rest buildable without a legal reviewer. A system that makes no legal claims requires no legal validation. It constrains every component's output, and it is enforced by test in criterion 12.

---

## 4. Scope

**In.** The six acts. Supreme Court and High Court judgments. English.

**Out.** Other areas of law. Advice on an individual's situation. Predicting rulings. Drafting. Other languages and jurisdictions.

**Deliberately not built.** Multi-tenant access control, because there is one public corpus. A published integration surface beyond a single read-only assessment tool. Support for additional subject areas.

**The advice boundary.** The ask behaviour may request only facts that determine which law applies: a date, a place, which offence. It must not ask what the user wants to achieve.

**Harm.** Wrong information here can affect a person's liberty. Decisions that look overcautious are overcautious on purpose.

---

## 5. Derived Data

All produced by code from published sources. No hand annotation required.

**Statutes.** Full text from the published statute layer, structured endpoints, CC BY 4.0. **Attribution is a licence condition** and appears in the repository, the interface, and every response citing it. Use the API, not the HTML. Each provision stores act, section, sub-section, text, heading, commencement, cessation.

**The unit question.** A **provision** is a section. A **passage** is what retrieval returns. Where a section has sub-clauses carrying different sentences, each sub-clause is its own passage carrying the section heading and number. Materiality operates on the whole section, because a section that gained sub-clauses has changed even though no existing sub-clause did. The findings operate on the section.

**Correspondence and materiality: two independent signals.** Signal one is the published cross-code mapping, giving closest provision by text similarity with a score, ranked alternates, and an explicit no-close-match verdict. Signal two is sentencing extraction from the texts: maximum and minimum imprisonment, maximum and minimum fine, mandatory or discretionary fine, whether imprisonment and fine combine, life, death, community service, and the number of sentencing limbs. Any difference in any field makes the change material.

Independent because one compares whole-text overlap and the other reads specific fields.

**Every extracted value carries the exact substring it came from, verified to occur in the source.** Anything not grounded in a verified span is reported as unparsed, never guessed.

Rows where signals agree settle automatically. Rows where they disagree enter an adjudication queue. Causes: similarity says unchanged while sentencing changed; similarity says changed while sentencing is identical; a split candidate needing confirmation; a partial parse; no sentencing language at all.

The first cause is the important one, and IPC 336 to BNS 125 is its shape: 95 per cent similar, labelled almost unchanged, with maximum imprisonment moving from three months to three years and maximum fine from 250 rupees to 10,000.

**Default disposition for an unworked queue.** New in 5.0. A row in the queue and not yet dispositioned is treated as **disputed**, which routes to the alternatives behaviour. This is deliberately the cautious default, and it has a consequence worth stating: **if the queue is never worked, the system shows alternatives for every queued provision.** The proportion of provisions in that state is reported as a system health metric, because a large unworked queue silently degrades the product from answering to hedging.

**Materiality is undefined for provisions with no sentencing language.** Definitions, general exceptions and procedural provisions carry no punishment. The material and immaterial distinction does not apply and the rules depending on it do not fire.

**The split threshold is derived**, not chosen, from the distribution of gaps between the best and second scores across every provision. A single successor produces a large gap; a split produces a small one. The threshold sits at the largest separation in that distribution, is recorded with the distribution it came from, and is recomputed when the source changes.

**Provision vocabulary.** Seeded from section headings in both codes, extended with terms appearing in judgments alongside a provision citation. A term mapping to several offences records all of them.

**In-force table.** Provision and date in, governing act out.

**Court splits: not available.** No open structured source exists. **F9 ships defined, unpopulated, switched off, documented as unpopulated.** Not approximated.

---

## 6. Ingestion

New in 5.0. Absent from every earlier version, and it is where a build stalls.

### 6.1 Statutes

Enumerate every section of each act from the published section index, then fetch each provision from the structured endpoint. Cache to disk on first fetch. Never refetch a public source to debug a regular expression.

Statutes are small, clean, and structured. This path is not hard and is not the risk.

### 6.2 Judgments

This path is the risk, and none of it was specified before.

**Extraction.** Judgment files vary. Some carry an embedded text layer and some are scanned images. **Every document records its extraction method and a quality score.** Documents below the quality threshold are excluded from the library rather than indexed badly, and the exclusion count is reported. A silently garbled judgment produces confident citations to nonsense.

**Scanned documents.** Reading text off a scanned image is a separate and slower process. The first library covers only documents that already carry readable text. The number of documents excluded for this reason is measured first, and that number decides whether reading the scanned ones is worth the effort.

**Structure detection.** Judgments carry numbered paragraphs, and paragraph numbers are the citation unit. Detection is by pattern with a fallback: where numbering cannot be found, the document is chunked by structural boundary and cited by offset rather than paragraph, and the citation says so.

**Provision citation extraction.** Every judgment is scanned for references to provisions, in both old and new numbering and in both formal and abbreviated forms. These become passage metadata, drive the retrieval filter, and feed the vocabulary. Without this the judgment corpus cannot be filtered by provision at all.

**Deduplication.** The same judgment appears in more than one form and courts republish. Deduplicate on case identifier plus court plus date, preferring the richest extraction. Report the duplicate rate.

**Adding new documents later.** The sources publish updates. Ingestion can be re-run safely at any time: it recognises documents it has already handled, adds only what is new, and does not require rebuilding everything from scratch.

### 6.3 Index build

The index is **built and versioned, never mutated in place**. Name pattern `chunks_v{n}_{embedding_model}_{date}`. Deployment points at a name, so rolling back retrieval is repointing a name. Two versions can exist side by side for comparison.

---

## 7. Provision Identification

Every finding depends on this. Getting it wrong applies the rules correctly to the wrong provision, which is worse than having no rules.

**Output.** Candidates, each with evidence and a confidence. Zero is valid.

**Order.** Explicit citation naming a code. Then bare number, returning the provision in each code because the number means different things in each. Then vocabulary lookup, returning every offence a term maps to. Then heading match. Then retrieval fallback, lowest confidence. Then nothing found.

**Discriminating two candidates.** New in 5.0, because F2 and F3 both produce two candidates and need different behaviour. The correspondence file decides: if the two candidates are recorded as correspondents of each other, this is one offence in two codes and F2 applies. If they are not, these are different offences and F3 applies. Without this check the bare-number trap and the ambiguous-term case are indistinguishable.

**Date resolution.** New in 5.0. Where a question carries a date it must be resolved to a calendar date before the in-force lookup. Explicit dates resolve directly. Relative expressions such as last year resolve against the current date and **the resolved date is stated back to the user in the response**. A year alone straddling the changeover, or a range straddling it, does not resolve; it is treated as no date given and the ask behaviour fires with the specific ambiguity named.

**Must not.** Pick the most common reading of an ambiguous term. Treat a bare number as belonging to the current code. Silently drop low confidence candidates.

**Measured separately**, because errors here masquerade as rule errors. Wrong-and-confident, meaning a wrong candidate at high confidence with the correct one absent, has its own target.

---

## 8. Retrieval

New design in 5.0. Version 4.0 said normalise then combine, which was hand-waving.

### 8.1 Statutes do not go through retrieval

**This is the significant change.** Identification already resolves the question to a provision identifier deterministically. Once the identifier is known, the provision is fetched **by key**.

Running a meaning search for a section that has already been named is waste, and worse, it can return a different section and override a correct answer. Search is for judgments and for the F14 residual only.

This removes most of the retrieval surface and removes the case where retrieval quality can corrupt a finding.

### 8.2 Judgment retrieval

Judgments are searched two ways at once, the two result lists are combined, and a second pass reorders the combined list.

**Meaning search.** Finds passages that are about the same thing as the question, even when the wording differs.

**Word search.** Finds passages containing the exact words. Kept because section numbers and case citations are exact strings, and meaning search handles them poorly. Someone asking about a specific section wants that section, not something that reads similarly.

**Combining the two lists.** Each search returns its results in order. A passage is scored by where it appeared in each list, and the two scores are added. A search can be given more weight than the other if it deserves it.

Three requirements on this step.

- **No score may have a flat amount added to it.** This is what broke the existing system. Scores from one search sat around 0.016, and the code added 0.35 whenever a pattern matched, so the pattern decided the ranking entirely and the meaning search had no effect at all. Any preference for exact matches is expressed by weighting a search more heavily, never by adding a constant to a score.
- **The combining formula has one setting that must be tuned, not left at its default.** The usual default squeezes all scores into a narrow band, which is what turned the added amount above from merely wrong into ruinous. It is tuned against the evaluation set and the value recorded.
- **The weights are recorded and measured**, not chosen once and forgotten.

**The reordering pass decides the final order.** A second, more accurate model reads each candidate passage against the question and reorders them. This changes what the combining step is for: **its job is only to get the right passage into the shortlist, not to rank it correctly.** Effort belongs in the reordering pass, not in tuning the combination.

**Filtering.** Applied before searching, at the store: provision, court, and date where the conversation has established them.

**Content from outside the library never enters this path.** External fetching is off by default. If enabled it is a separate labelled signal that cannot be cited and cannot affect the behaviour decision.

### 8.3 Caching

New in 5.0. Identification, correspondence lookup, in-force lookup and the findings engine are deterministic functions of their input, so the same question yields the same result always. That is a cache with a trivially correct key.

Cache the deterministic prefix, keyed on the normalised question plus the data version. Repeat questions then cost nothing rather than a model call. Invalidate on any change to the correspondence file, the vocabulary, or the thresholds.

---

## 9. Conversation and Resume

New design in 5.0. Version 4.0 made ask a core behaviour and never said what happens when the user answers. This was the most serious gap in the document.

### 9.1 Bound facts

A conversation carries a small set of **bound facts**: offence date, court, offence identity, code. Each records its value, how it was obtained, and the turn that bound it.

Bound facts are inputs to identification and to the findings on every subsequent turn. A date bound on turn two is a date given on turn three, so F5 fires rather than F10 and the system does not ask twice.

### 9.2 The resume protocol

When the previous turn asked a question, the next turn is checked in this order.

1. **Does the reply answer the question asked?** If yes, bind the fact and re-run identification and findings with it bound. The original question is re-answered, not restated.
2. **Is the reply a new question?** If yes, discard the pending ask, keep bound facts that remain applicable, and treat it as a fresh turn. A user who changes the subject must not be held to the previous question.
3. **Does the reply say the user does not know?** Handled in 9.3.
4. **Is the reply uninterpretable?** Ask once more, phrased differently. Never more than twice for the same fact.

### 9.3 When the user cannot answer

New in 5.0 and entirely missing before. Ask assumed the user has the fact. Often they do not.

If a user cannot supply the fact, **the system falls back to showing the alternatives**, one per possible value, with the conditions under which each applies. It does not refuse, and it does not guess.

This makes ask an optimisation over alternatives rather than a hard gate. Ask is preferred because one precise answer beats two hedged ones, but an unanswerable ask degrades to something still useful.

### 9.4 Where conversation state lives

With the rest of the conversation state, saved to the same database that holds the audit records. There is no separate memory component. The earlier version of this system had one, and it was never reachable from the interface people actually used, so building a second would repeat that mistake.

Bound facts are part of the audit record, because an answer that depended on a date bound three turns earlier must be reconstructable.

### 9.5 Limits

Conversations are short by design: ask, answer, resolve. A turn limit applies, after which the conversation is treated as fresh. There is no summarisation, no compaction, and no long-term memory, because there is nothing here that needs them.

---

## 10. Response Schema

New in 5.0. Absent from every earlier version, which is remarkable given that the four behaviours have four different shapes.

Every response carries:

- **behaviour**, one of the four
- **findings**, every contributing finding with its reason in plain words
- **assumption**, present only for answer-with-assumption, stated first in the rendered output
- **content**, shaped by behaviour: a single answer; a single question; or an ordered list of alternatives
- **citations**, each with passage identifier, act, section and sub-section, case identifier and paragraph where applicable, in-force dates, and the quoted span
- **data provenance**, including the attribution required by the source licence, and for any correspondence-derived statement, that it is computed by text comparison and not official
- **coverage note** where relevant, for example that court splits are not covered
- **advice notice**
- **bound facts** currently in effect, so the user can see what the system is assuming about their situation

**Ordering of alternatives.** Ordering implies precedence, which would be a legal conclusion. Alternatives are ordered by an explicit stated rule, currently chronological by the commencement date of the governing act, and the rule is stated in the response.

**Quotation length.** Statutory text is public domain, so length is a usability question. Quote the operative span plus enough context to be readable, and link to the full provision.

---

## 11. Deciding What To Do

### 11.1 Findings, not first match

Every applicable rule records a finding. All are collected. Behaviour is decided from the complete set. A question can be both temporally uncertain and subject to an open disagreement, and both must be reported.

### 11.2 The findings

**F1** No candidate provision. Retrieval-led, see F14.
**F2** Bare number valid in both codes, candidates not correspondents of each other. **Alternatives**, showing what it means in each.
**F3** Candidates are distinct offences. **Ask** which.
**F4** Code named explicitly. **Answer** under that code.
**F5a** Resolved date before commencement. **Answer** under the old code.
**F5b** Resolved date on or after commencement. **Answer** under the new code, unless correspondence is disputed, in which case F6 also fires.
**F6** Correspondence disputed, including undispositioned queue rows. **Alternatives**, stating the correspondence is unsettled.
**F7** Split. **Alternatives**, one per successor with its conditions.
**F8** No successor, or a new offence with no predecessor. **Answer**, stating plainly it does not carry across.
**F9** Known court split. **Alternatives**. Unpopulated and off.
**F10** Material change, no date. **Ask** for the offence date only.
**F11** Immaterial change, no date. **Answer with a stated assumption**, under the current code, giving both numbers.
**F12** Offence not identified. **Ask** which offence.
**F13** Low confidence identification. **Ask** or **alternatives**. Never a plain answer.
**F14** Retrieval-led. Strong consistent on-point passages give **answer**. Otherwise state the library has no reliable answer. Never fabricate.
**F15** New in 5.0. **Procedure and substance both engaged.** Which act governs an offence and which governs how a case is investigated and tried are separate questions that can point at different codes for the same matter. The system does not determine how they interact. **Alternatives**, presenting the substantive position and the procedural position separately, each with its own sources, and stating explicitly that their interaction is a matter of legal judgement the system does not make. This follows directly from Section 3.1.
**F16** New in 5.0. **Several provisions named in one question**, for example a comparison. Not ambiguity. The findings run per provision and the response covers each, with any provision-level finding reported against that provision.

F10 and F11 require a materiality verdict. Where materiality is undefined, neither fires and F4, F5 or F14 governs.

### 11.3 Combining

Alternatives and ask are most cautious, then answer with a stated assumption, then answer. The chosen behaviour is the most cautious any finding requires. Where alternatives and ask both apply they combine: alternatives shown, follow-up offered beneath. Every contributing finding is reported.

### 11.4 Thresholds

Every threshold is computed from the project's own data, recorded with the distribution it came from, and reproducible. None is chosen by hand.

### 11.5 Whether anything learned is needed

F14 is the residual. **The residual study:** run the golden set, collect everything reaching F14, determine its size, how often its correct behaviour differs from simply answering, and whether it has shared structure.

**Gate.** Small or unstructured means nothing more is built. Large and structured means a learned component is specified as a change to this document. It will not be built on an assumption that it must be needed.

---

## 12. The Evaluation Harness

**Golden set format.** One JSON object per line: id, question, expected behaviour, expected provisions, expected assumption, label source, notes. Duplicate ids and invalid behaviours raise rather than being skipped.

**Sizing, new in 5.0 and it changes the plan.** The harness reports a rate as insufficient data below twenty items. There are sixteen findings. **A golden set that can report per-finding correctness therefore needs at least twenty items per finding that can realistically fire, which puts the floor around three hundred items, not the eighty a first pass would produce.** Coverage per finding is a build requirement, not an aspiration, and the harness reports which findings are below the floor.

**Runner.** Golden set plus a system under test supplied as module and factory, so model versions are captured by the system rather than passed on a command line. Deterministic.

**Measures.** How often the right response was chosen. How often the system answered when it should have been cautious, tracked on its own because folding it into an overall figure hides it. How often it asked when it should simply have answered. How often the correct provision was the first one found, and how often it was found at all. How often a wrong provision was found while the right one was missed. How often a stated assumption was the right one to make.

**Every figure is reported with a margin of error and the number of items it was calculated from.** The method used is chosen because the figures that decide whether to release are the ones close to zero, and the more common method is unreliable there.

**Per-finding breakdown.** How often each fired and how often behaviour was right when it did. Without this a regression in one rule disappears into the average.

**Extractor evaluation, new in 5.0.** The sentencing extractor is evaluated separately across every provision: parse rate, partial-parse rate, and span verification rate. This is cheap, needs no labels, and catches the class of bug found in the number parser during development.

**Label source distribution** reported every run, so a metric derived from the same signal the rules use is visible.

**Model baseline, new in 5.0.** A frontier model with the same retrieval and a good prompt runs on the same golden set. It leads with **label-free comparisons**: determinism under repeated runs, evidence verification rate, abstention stability under rephrasing, cost, latency. Accuracy follows, **partitioned by label source, with circular partitions marked circular in the report itself**. Without this every number the system produces is unanchored.

**Baseline and gate.** Asymmetric tolerances: unsafe confidence and wrong-and-confident have zero tolerance and any increase blocks; others allow small movement. Regression exits non-zero. Updating the baseline is a separate explicit action.

**Report artifact.** Metrics, intervals, per-finding breakdown, label sources, failing items, and which golden set and system produced it.

---

## 13. Using a Model as a Second Reader

Legitimate in one role and dishonest outside it.

**Where it works.** As a second extraction signal. The model sees only primary text, answers closed checkable questions, and quotes the span it relied on. The quote is verified mechanically. Not trusting the model; using it as an extractor whose output is checked.

**Conditions, all required.** Primary text only, never the rules or the extractor output. Closed questions, never is this good. Quotes its evidence, and the quote is verified. Disagreement sends the row to the queue, never averaged into a tiebreak. Never the same model that generated the answer. Agreement rate reported as a metric, because near-total agreement means one signal, not two.

**Where it must not be used.** Judging grounding of output from the same model family, because failures correlate. Judging behaviour correctness while shown the rules, because it agrees with itself. Anything where correct is a legal opinion, because the model has no standing and answers confidently either way, which is the failure this project exists to prevent.

Repeated sampling measures stability, not correctness.

**Disclosure.** Model-derived labels are declared as such. Not expert validated.

---

## 14. Guardrails

**Inbound.** Detect instruction manipulation; blocked and logged, detection imperfect. Detect and remove personal data before processing or logging, imperfect, which is why minimising collection matters more. Confirm subject area. Identify personal advice requests using the Section 4 boundary; a judgement call, errs towards declining, declines go to the review queue.

**Retrieval.** External fetching off by default. If enabled, content is untrusted: separated by explicit markers, scanned, capped in influence, never outranking library material.

**Connecting to outside services, new in 5.0.** If the system is ever connected to an external service, the description that service gives of itself is untrusted, because it can carry hidden instructions. Services are fixed in advance rather than discovered automatically, and their descriptions are reviewed before use. Anything such a service returns is treated with the same caution as content from the open web.

**Generation.** Every factual statement should trace to a cited passage; untraceable statements are removed or the answer regenerated.

**Bounded, new in 5.0.** Because Section 5 gives every passage a stable identifier and the generator cites by identifier, **verification is primarily a mechanical join, not a model call.** A model call is used only where a claim cannot be matched to a cited passage by identifier. Unbounded per-claim model verification could cost more than generation itself.

Two hard guarantees, both lookups: **cited provisions must exist and quoted text must match the source**, and **any answer citing a repealed provision must say so with the date**.

**Outbound.** Personal data checked again. Advice notice attached. Behaviour, findings and assumptions shown plainly.

**Failing closed, and the way back.** Guardrails fail closed. A false positive is a blocked legitimate user, so blocks get a specific message, enter a review queue, and can be released. False positive rate measured per guardrail. A high rate is a defect to tune, not tolerate.

**Recording.** Every request produces an audit record: question after personal data removal, candidates and confidence, bound facts, all findings, behaviour, assumption, guardrail outcomes, sources, component versions, index version, response time, cost.

---

## 15. Performance Budget

New in 5.0. Version 4.0 had no target, and the current codebase makes up to seven model calls per question.

**Model calls per question.** Behaviour decision: **zero**, the findings engine is deterministic. Generation: one. Relevance check and rewrite: at most two, and only on the retrieval path. Grounding: only for claims not matched by identifier. **Target two to four total, budget five, alert above.**

**Response time.** A target is agreed before launch, measured so that the slowest one in twenty is what counts rather than the average, and alerted on when missed. Repeat questions answered from the cache should need no model call at all.

**Cost.** Per-question cost tracked continuously, with limits per caller and overall, and automatic cutoff.

---

## 16. Security

Proportionate: one public corpus, no private documents, no other organisations.

**Secrets.** None in source or any file stored with it. Managed store, injected at runtime. Automated scanning blocking merge. History scanned once and cleaned. Any credential ever committed is treated as compromised and rotated.

**Supply chain.** Dependencies pinned with a lock file. Vulnerability scanning on every change. Containers from pinned bases, non privileged.

**Access.** The endpoint authenticates. Rate and cost limits per caller. Timeouts on every external call, and external failure degrades rather than hangs.

**Data.** Encrypted in transit and at rest. Personal data removed before logging, with logs tested for leakage. What is sent to model providers minimised and documented including retention.

**Deletion.** Live systems support record-level deletion. Backups do not, and claiming otherwise would be false. Backups expire on a retention window or are handled by destroying decryption keys. The approach is chosen, documented and tested. **Applies in the deployed scenario only.**

**Regulation.** If the system stores questions or user personal data, India's data protection regime applies and obligations must be confirmed with a qualified adviser. The cheapest and recommended posture is to store no personal data at all. This document identifies the regime and does not interpret it.

**Protected artifacts, new in 5.0.** `adjudication_dispositions.jsonl` and the hand-checked rows of the golden set are the only artifacts representing human judgement rather than computation. They are never writable by an automated agent. Enforced by a pre-commit hook, not by convention.

---

## 17. Acceptance Criteria

Split by scenario, new in 5.0. Version 4.0 mixed them, so criteria requiring tested backups could never be met in the mode you will actually be in.

### 17.1 Core, required in every scenario

1. Six acts and a filtered slice of judgments in the library, with attribution present.
2. Ingestion records extraction method and quality per document, excludes below-threshold documents, and reports the exclusion and duplicate rates.
3. Passage granularity follows Section 5 and no provision is split incorrectly, verified by test.
4. Correspondence complete. Every row either settled by two agreeing signals or in the queue with its cause recorded. Undispositioned rows default to disputed and the proportion is reported.
5. Every extracted sentencing value carries a span verified against source. Unverifiable extractions report as unparsed.
6. The split threshold is derived from the score-gap distribution and recorded with it.
7. Vocabulary and in-force table built and tested.
8. F9 ships unpopulated, off, documented.
9. Provision identification implemented, measures meet targets, wrong-and-confident below its own limit, correspondent-versus-distinct discrimination tested, date resolution tested including the straddling-year case.
10. **Statutes are fetched directly by their identifier and never through search**, verified by test.
11. Judgment search combines two result lists by rank with recorded weights and a tuned setting, applies **no flat additions to any score anywhere**, verified by test, and is followed by a reordering pass.
12. F1 to F16 implemented with test cases each; combination reports every contributing finding.
13. The bare number case handled correctly, with dedicated tests.
14. Conversation resume implemented per Section 9, including the cannot-answer fallback to alternatives, tested.
15. Response schema per Section 10, including alternative ordering by a stated rule.
16. **No response asserts a legal conclusion**, verified by test against the output vocabulary.
17. Golden set meets the per-finding floor, or the harness reports which findings fall below it.
18. Extractor evaluation runs across every provision.
19. Model baseline runs, leading with label-free comparisons, accuracy partitioned by label source with circular partitions marked.
20. Residual study complete, conclusion recorded.
21. Harness runs in CI and blocks on regression. Behaviour correctness meets target with an interval; unsafe confidence and unnecessary asking below limits.
22. Guardrails implemented and tested including adversarial attempts, false positive rates measured, review queue working.
23. Grounding meets target. Citation correctness and repeal currency hold absolutely. Verification is bounded per Section 14.
24. Model calls per question within budget, alerted above.
25. No secret in repository or history; scanning in place; any committed credential rotated.
26. Dependency scanning with no unresolved high severity findings.
27. Protected artifacts enforced by pre-commit hook.
28. Documentation complete, including that model-derived labels are declared.

### 17.2 Additional, deployed scenario only

29. Index built in CI as a versioned artifact; deployment points at a name; rollback is repointing.
30. Health check reports genuine readiness, not process liveness.
31. Usage figures, request traces and alerts in place, including an alert on any sudden shift in how often each response type is chosen.
32. Backup deletion approach chosen, documented, tested.
33. Data protection obligations reviewed if any personal data is stored.

---

## 18. Known Limitations

**Correspondence is computed, not official.** No government machine-readable mapping exists. A high similarity score means the words are alike, not that a court has held the provisions equivalent. The system says so.

**Materiality derives from sentencing language only.** A provision whose elements changed while its sentence did not reads as immaterial. Both texts are always shown.

**Provision identification is imperfect.** Uncertainty produces caution, but a wrong high-confidence identification still produces a wrong answer, which is why that rate is tracked separately.

**Court splits are not covered.** F9 is unpopulated. Answers must not be read as confirming a point is settled.

**Procedure and substance interaction is not determined.** F15 presents both and declines the interaction.

**The library is a slice**, and scanned judgments are excluded until reading text off images is added.

**Grounding checking is not perfect.**

**Personal data and advice-boundary detection are imperfect**, and both err towards caution, so legitimate questions will sometimes be declined.

**Guardrails can be defeated.**

**Statutory interpretation is not mechanical.**

**Answering on a stated assumption transfers risk to the user**, so its presentation is a safety feature.

**An unworked adjudication queue degrades the product.** Everything queued shows alternatives. The proportion is reported for that reason.

**No legal validation exists.** No qualified person has attested the derived data is correct as a matter of law. Section 3.1 is what makes this acceptable rather than reckless, and it holds only while the system asserts no legal conclusion. Criterion 16 is not optional.

---

## 19. Deliverables

1. Running system and interface.
2. Ingestion pipeline with quality reporting.
3. Versioned index and build.
4. Correspondence file and adjudication queue.
5. Sentencing extractor and materiality comparison.
6. Vocabulary and in-force table.
7. Provision identification with date resolution.
8. Retrieval: direct lookup for statutes, combined two-way search and reordering for judgments.
9. Findings F1 to F16 and combination.
10. Conversation and resume.
11. Response schema.
12. Residual study and conclusion.
13. Guardrails and review queue.
14. Harness, golden set, baseline, model baseline, CI gate.
15. Test suite and automated checks.
16. Deployment configuration and monitoring.
17. Documentation.

---

## 20. Questions For The Client

1. Acceptable rate for unsafe confidence. The most important number and a business decision.
2. Acceptable rate for unnecessary asking.
3. Acceptable rate for wrong and confident identification.
4. May the system fetch material from outside its library. Recommendation: no.
5. Which model providers are acceptable and their retention terms.
6. Should user questions be stored at all. Storing none is cheaper and safer.
7. Who is accountable for a wrong answer, and what is the correction procedure.
8. Is the deployed scenario in scope, or is the laptop scenario the deliverable.

---

*End of specification.*
