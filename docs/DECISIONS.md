# Decision Records

Every decision in this project that reversed an earlier one, with the reasoning that produced it.

This file exists because the requirements document was rewritten five times and each rewrite deleted the thinking behind the last one. A specification tells you what was decided. It does not tell you what was tried, why it looked right, or what killed it. That second thing is worth more, both for anyone picking this up later and for anyone deciding whether the decisions were made carefully.

Each record has the same five parts: what was proposed, why it looked right at the time, what changed it, what replaced it, and what would change it back. The last part matters most. A decision with no conditions attached is a prejudice.

Read in order. Several of these depend on earlier ones.

---

## D1. Learned clustering at the centre, replaced by deterministic rules

**Proposed.** Group a pool of questions into a small number of meaning groups automatically, measure how strongly each incoming question belongs to each group, and use the spread of that distribution to decide whether the question is ambiguous. Deterministic legal rules would sit underneath as overrides for known cases.

**Why it looked right.** It needs no labels. Groups emerge from the data rather than from somebody's opinion about what categories should exist. Thresholds can be computed from the distribution rather than chosen. It generalises, in principle, to any subject area with a question pool.

**What changed it.** Two things, and the second is the more serious.

First, the override rules covered every ambiguity source in the problem statement: the code changeover, split provisions, dropped provisions, court disagreements. Once those were written, the learned layer had no defined job. It was deciding a residual that had never been described or measured, and there was not a single worked example of a question the rules missed that clustering caught.

Second, and this is the fatal one, the central assumption was wrong. Grouping unlabelled legal questions by meaning produces topic groups: theft questions, bail questions, evidence questions. A question sitting between the theft group and the cheating group is not ambiguous. It is a question about a boundary offence with one correct answer. Spread across groups measures topical breadth. Ambiguity means the number of valid readings. Those are two different properties and nothing in the design forced them to line up.

There was a third, smaller problem. The passage-side signal, meaning how retrieved passages spread across groups, changes with the retrieval depth. Change the number of passages retrieved and the ambiguity verdict changes with it. That is an unstable signal presented as a measurement.

**What replaced it.** The rules became the product. The learned layer became conditional, gated behind a residual study that measures how many questions the rules do not handle and whether those questions share any structure. The expected outcome of that study is that nothing gets built, and that is a success rather than a disappointment.

**What would change it back.** A residual study showing the residual is both large and structured. If it is large but unstructured, better matching will not help. If it is structured but small, the effort is not worth it. Both conditions are required. And any learned component proposed after that must first address the topic-versus-ambiguity confusion above, because clustering questions by meaning still will not measure ambiguity no matter how good the clustering is.

---

## D2. Always asking for the offence date, replaced by answering on a stated assumption

**Proposed.** If a question concerns an offence that exists in both codes and the user has not said when the offence took place, ask for the date before answering.

**Why it looked right.** It is the safe rule. The answer genuinely depends on the date, so asking for the date is the honest response. It follows directly from the problem statement.

**What changed it.** Nobody states an offence date. That rule would have fired on nearly every criminal law question the system received, which means the system would ask "when did this happen" before answering almost anything.

That is exactly the failure listed as a risk in the same document under the heading of unnecessary asking. The rule caused the risk the document warned about.

**What replaced it.** A fourth behaviour. Where a provision carried across with the same substance and the same punishment, and only the number changed, the system answers under the current code, states the assumption at the top in plain words, and gives both section numbers. Where the punishment or the elements changed materially, it still asks, because there the two answers genuinely differ.

The split between those two cases is decided by the materiality signal in D5.

**What would change it back.** Evidence that users do not read stated assumptions. The whole approach transfers a small amount of risk to the reader, and it depends on the assumption being visible and read. If usage showed people acting on the answer while ignoring the assumption line, the safe rule would come back for a wider set of provisions.

---

## D3. Assuming an official concordance exists, corrected

**Proposed.** Version 1.0 stated that the government published a table mapping old code sections to new ones, and treated that table as authoritative ground truth. The whole project rested on it.

**Why it looked right.** It is what you would expect. A legislature that replaces a criminal code would publish a correspondence. Comparison charts do exist and are widely referenced.

**What changed it.** It was checked and it is not accurate. India Code, the government's own repository, hosts both the old and new codes and provides a comparison between provisions, but that comparison is derived by text similarity rather than issued as an official legal correspondence. There is no machine-readable government mapping. Practitioner tables, publisher concordances and commercial converters all exist and do not fully agree with one another.

**What replaced it.** The file moved from "authoritative source" to "reviewed working reference with recorded confidence and an explicit disputed category". Disputed became a first-class state rather than an error, because where credible sources disagree, showing the competing readings and saying the correspondence is unsettled is more useful and more honest than picking a side.

**What would change it back.** Publication of an official machine-readable correspondence. If that happens, it supersedes the computed mapping entirely and most of the adjudication queue disappears.

---

## D4. Hand-built correspondence requiring a legal collaborator, replaced by derivation from public sources

**Proposed.** Build the correspondence file by hand. Estimated at somewhere between one hundred and fifty and three hundred hours of qualified legal time, with the recommendation to find a law student or junior advocate as a collaborator.

**Why it looked right.** No official mapping exists, per D3. The distinctions involved are legal judgements. Several correspondences are genuinely contested among practitioners.

**What changed it.** A direct challenge, and the challenge was correct. The question asked was why public sources had not been checked, and the honest answer was that they had not been checked exhaustively.

They were then checked. A machine-readable statute layer exists, serving sections in structured form, requiring no credentials, with bulk datasets published under a permissive licence. It also publishes computed cross-code mappings: for each provision of the old code, the closest provision of the new code by text similarity with a score, plus ranked next-closest matches, plus an explicit no-close-match verdict where the law genuinely changed.

That covers correspondence candidates, split candidates and no-successor candidates for the whole old code, derivable by code.

**What replaced it.** Automated derivation from published sources, with a human involved only in the disagreement set. The estimate of one hundred and fifty to three hundred hours was withdrawn. An earlier estimate of "a weekend and three hundred and fifty rows" had already been withdrawn in the other direction, which is worth noting because it means the first two estimates were both wrong and in opposite directions.

**What would change it back.** The source becoming unavailable, or its licence changing. Both are real risks for a single-source dependency, which is why practitioner tables are retained as a cross-check and disagreement between two independent published tables is treated as an automatic trigger for the disputed marker.

---

## D5. Two human reviewers on materiality, replaced by an extractor and an adjudication queue

**Proposed.** The correspondence file would carry a column recording whether a change between provisions was material, meaning the punishment or the elements differed enough to change the answer. Because that single column decides whether a user gets a full answer or a request for a date, it would be assessed independently by two reviewers.

**Why it looked right.** It is the highest-consequence field in the data. Two independent readers is the standard way to handle a subjective judgement.

**What changed it.** Materiality is not actually subjective for most provisions, and it is not derivable from similarity either.

Not from similarity, because a provision can score highly on text overlap and still have changed enormously. The worked case is in the discovery log.

Not subjective, because both texts are available and sentencing language in these codes is formulaic. Maximum imprisonment, minimum imprisonment, maximum fine, minimum fine, whether fine is mandatory or discretionary, whether imprisonment and fine combine, availability of life or death or community service, and the number of sentencing limbs are all extractable. Any difference in any field makes the change material. That is reading, not judgement.

**What replaced it.** An extractor producing those fields from both texts, with a hard constraint that turns it from something to trust into something to check: **every extracted value carries the exact substring it came from, and that span is verified to occur in the source.** Anything not grounded in a verified span is reported as unparsed rather than guessed.

Two independent signals now decide each row. Similarity answers which provision is the successor. Extraction answers whether the punishment changed. Rows where they agree settle automatically. Rows where they disagree go to an adjudication queue, and that queue is where the real judgement lives.

**What would change it back.** A disagreement rate high enough to suggest the extractor is not reliable, or a discovery that materiality in the sense the rules need depends on elements rather than sentencing far more often than expected. The known limitation stands: a provision whose elements changed while its sentence did not will read as immaterial, and the mitigation is that both texts are always shown.

---

## D6. First rule wins, replaced by collecting findings

**Proposed.** The rules run in order and the first one that applies decides the behaviour.

**Why it looked right.** It is simple, it is fast, and it is how most rule engines are written. Ordering encodes priority.

**What changed it.** It silently discards information. A question can concern a provision that both changed materially and is subject to a known court disagreement. First-match-wins reports one and hides the other, and there is no signal to the user that anything was hidden.

It also produced a specific ordering bug. The rule for a stated date fired before the check for a disputed correspondence. That is harmless for a date before the changeover, because the old code applies directly and no correspondence is needed. For a date after the changeover on a disputed provision, the ambiguity was swallowed entirely.

**What replaced it.** Every applicable rule records a finding. All findings are collected. Behaviour is the most cautious that any finding requires. Every contributing finding is reported to the user, not only the deciding one.

The ordering bug then fixed itself rather than needing a special case, which is usually a sign the new structure is right.

**What would change it back.** Nothing identified. Collecting findings costs almost nothing and the special-case burden of first-match ordering grows with every rule added.

---

## D7. Knowledge graph, cut

**Proposed.** A property graph holding acts, provisions, offences, courts and cases, with relationships for supersession, citation, in-force periods and interpretation. Justified on three grounds: temporal lookup, cross-reference traversal, and provenance for audit.

**Why it looked right.** Legal material is genuinely relational. Provisions cite other provisions which cite schedules. Audit wants lineage. It is also the answer that sounds most like enterprise architecture, which should have been a warning rather than a reassurance.

**What changed it.** Each of the three justifications collapsed when examined.

Temporal lookup is a table with a handful of rows. Six acts, six commencement dates. It does not need a graph database or a second query language.

Cross-reference traversal is genuinely useful and genuinely a nice-to-have. It improves answers on some questions. It does not enable anything the system otherwise could not do.

Provenance is a column, not a graph.

There was also a contradiction to resolve. The advice given was to cut it, and then the same document made it a deliverable and made one of the core rules depend on it for the in-force lookup. It cannot be both cut and depended upon.

**What replaced it.** Two small tables. An in-force table and a known-splits table. Both fit in a file.

**What would change it back.** A measured retrieval failure specifically caused by not following citation chains, on a set of questions large enough to matter. Not a feeling that traversal would help. A measurement.

---

## D8. Five integration capabilities, cut, then reframed from server to client

**Proposed.** Expose the system through five capabilities: search the library, retrieve a document, identify provisions, assess a question, check applicable law. With a permission model, versioned schemas, per-caller limits and provenance on every response.

**Why it looked right.** It turns an application into a capability other systems can consume, which is a more durable thing to have built.

**What changed it.** There was no caller. Building the server means auth, scopes, schemas, limits and a test suite for all of it, connected to nothing. It is also downstream of everything, because the interesting capability returns a behaviour and its findings, and the component that produces those did not yet exist.

Four of the five were also uninteresting. A search endpoint, a document fetch, a date lookup and a table lookup are not worth a protocol.

**What replaced it.** First, one read-only tool for assessing a question, built after the findings engine works.

Then a second reframe, prompted by a different intention: connecting to Hugging Face, Drive, Jira, Confluence, SharePoint. That is a client, not a server, and it splits into three categories that are not equal.

Runtime connection, where the agent calls a connector mid-question, mostly fails here. A page from an internal wiki has no version, no effective date and no authority, so it cannot be grounding-checked in any meaningful sense, and it is untrusted input to a model in exactly the way an external web page is.

Ingestion, where documents flow into the library through the same pipeline as statutes, is where document sources belong.

Operational, outside the request path entirely, is the strongest category and the one nobody thinks about. The adjudication queue is a queue of rows needing disposition, which is what an issue tracker is for.

**What would change it back.** For the server: an actual caller. For runtime connectors: a source that carries version and effective date, which internal wikis generally do not.

---

## D9. Multi-tenant access control, cut

**Proposed.** Access filtering enforced at the storage layer so a coding mistake cannot expose documents, with organisation established at authentication and never supplied by the request, verified by an automated cross-organisation test.

**Why it looked right.** It is correct practice, and for a legal system holding client documents it would be mandatory rather than optional.

**What changed it.** There is one corpus and it is public. There are no organisations. The requirement was specifying protection for a boundary that does not exist.

**What replaced it.** Authentication on the endpoint, rate limits and cost limits per caller. Nothing more.

**What would change it back.** Any private document entering the library. At that point this returns in full, including storage-layer enforcement, because application-level filtering is one bug away from a breach.

---

## D10. Record-level deletion from backups, replaced by retention expiry

**Proposed.** Deletion requests supported end to end, including in backups, with a tested procedure.

**Why it looked right.** It is what data protection obligations appear to require and it is what people write in specifications.

**What changed it.** It is not achievable. Backups are point-in-time images. You cannot reach into a snapshot and remove one record without restoring, modifying and re-taking it, which is not a procedure anybody runs on a deletion request.

**What replaced it.** Live systems support record-level deletion. Backups are handled by defined retention windows after which they expire, or by destroying the keys that decrypt them. The approach is chosen, documented and tested.

**What would change it back.** Nothing. The original was simply false.

---

## D11. Review set built by an independent person, replaced by building it first and sealing it

**Proposed.** The set used to measure the system must be built by someone who did not build the rules, from sources not used during development.

**Why it looked right.** If you write the rules and also label the questions that test them, you are measuring self-consistency and calling it accuracy.

**What changed it.** On a team of one it cannot be done. A requirement nobody can satisfy is worse than no requirement, because it makes the specification permanently unsatisfiable and teaches everyone to ignore criteria.

**What replaced it.** Build the review set first, before the rules exist, then seal it and do not consult it until a candidate release is tested. That achieves most of the same protection and can actually be done. If it is consulted during development it is burned and a new one is built.

Provenance is also declared per item rather than assumed. Every item records where its label came from, so a metric derived from the same signal the rules use is visible in the report rather than hidden inside an accuracy figure.

**What would change it back.** A second person joining. Then the original is better and should be restored.

---

## D12. Model baseline as a headline accuracy comparison, replaced by label-free comparison first

**Proposed.** Run a strong general model on the same golden set with the same retrieval, and report a comparison table.

**Why it looked right.** Every number the system produces is unanchored without it. Behaviour correctness of eighty-eight per cent means nothing until you know what a good model with a good prompt scores on the same questions.

**What changed it.** A direct question about whether adding it would make things circular. The answer is yes, partly, and specifically in the place that matters most.

Golden set labels carry a source. Where a label came from the sentencing extractor, the system scores perfectly by construction, because the extractor produced the label and the system uses the extractor. The model scores lower for disagreeing with the labeller, not for being wrong. And unsafe confidence, the metric identified as the most important in the whole project, is defined against the label. Where the label came from the extractor, unsafe confidence measures agreement with the extractor.

A table showing the system far ahead would have been a rigged benchmark, and anyone who asked where the labels came from would have found it in one question.

**What replaced it.** The comparison leads with things that need no labels at all: determinism under repeated runs, evidence verification rate, abstention stability under rephrasing, cost and latency. Those measure exactly the claims that survive, which are reliability claims rather than capability claims, per D16.

Accuracy follows, partitioned by label source, with the circular partitions marked as circular in the report itself rather than in a footnote. A third output is a disagreement set: every item where the system and the model differ, adjudicated against the statute text rather than against either party's labels.

**What would change it back.** A golden set labelled entirely independently of the pipeline. Then straightforward accuracy comparison becomes legitimate.

---

## D13. Web search as a retrieval fallback, replaced by off by default

**Proposed.** The original codebase scrapes pages and adds the text to the context when retrieval quality is poor.

**Why it looked right.** It fills gaps. When the library cannot answer, the web sometimes can.

**What changed it.** Three things.

It is the largest attack surface in the system and the attack is cheap. Someone who ranks a page for a common legal query containing instructions controls the agent, and the search results around this subject area are full of automatically generated material.

The corpus is already authoritative for statutes. Nothing on the open web outranks a bare act. A web result can only add noise or contradict something already held correctly.

It breaks the principle everything else rests on. The system asserts text facts with a verified span from a source with known provenance and a known in-force date. A scraped page has none of those, so grounding checking against it is theatre.

And the specific proposed use was backwards. Reaching for the open web at the moment the system is least certain is how a confident wrong answer gets manufactured. The fallback path is the highest-risk path in any retrieval system.

**What replaced it.** Off by default, switchable without deploying code, implementation deleted rather than ported.

**What would change it back.** One case genuinely justifies it: whether a court disagreement has since been settled, which is the gap left open when court splits were declared unavailable. If it returns, it returns as a separate labelled signal against an allowlist of authoritative sources, which cannot be cited, cannot produce a claim, and cannot affect the behaviour decision. All it may do is note that more recent material may exist.

---

## D14. Statutes retrieved by search, replaced by lookup by key

**Proposed.** All content, statutes and judgments alike, goes through the same hybrid retrieval path.

**Why it looked right.** One path is simpler than two. It is also the default shape of every retrieval system.

**What changed it.** Provision identification already resolves the question to a provision identifier deterministically, from an explicit citation, a bare number, or the vocabulary. Once the identifier is known there is nothing to search for.

Worse than wasteful, it is dangerous. A vector query for a provision already named can return a different provision and override a correct deterministic result. The search path can corrupt a finding.

**What replaced it.** Statutes are fetched by key. Search is for judgments and for the residual case only. This removes most of the retrieval surface and removes the class of failure where retrieval quality damages a rule.

**What would change it back.** Nothing identified. It is strictly better.

---

## D15. Context engineering as a programme, reduced to two specific changes

**Proposed.** Adopting context engineering practices generally.

**Why it looked right.** It is where a lot of current attention sits, and some of it is genuinely valuable.

**What changed it.** It is a bucket term covering at least six unrelated techniques, and most of them do not apply here. Statutory sections are short, so there is no context pressure to relieve. Conversations are three turns, so there is nothing to compact. A memory subsystem was already tried in the original codebase and was unreachable from the API, so adding a second repeats the mistake.

The deeper point is that the behaviour decision does not pass through a context window at all. The findings engine, the correspondence file, the in-force table and the extractors touch no model. So context work cannot improve the part of the system that makes it different. It can only improve the written quality of the final answer.

**What replaced it.** Two changes. Stable passage identifiers in the generator's context, so grounding verification becomes a mechanical join rather than fuzzy text matching. And keeping the reasoning out of the generator's context, so that the generator writes each branch from its passages alone and cannot rationalise a conclusion it did not reach.

**What would change it back.** Judgment retrieval growing to the point where whole documents are being pulled into context. Then just-in-time loading of paragraphs becomes worth building.

---

## D16. The claim about what models cannot do, narrowed

**Proposed.** The system is needed because models guess when legal questions are ambiguous.

**Why it looked right.** It is the motivating story and it was true when the project started.

**What changed it.** A direct challenge about whether a model could simply do this, and honest examination shows most of the capability arguments fail. A capable model with search will explain the code changeover correctly. Given both provision texts it will read the punishment change correctly. It spots the bare-number collision as soon as both codes are retrieved, which makes that a retrieval problem rather than a reasoning one.

Small models do fail all of this, mostly because the old code outweighs the new one in training data by more than a century of text. But nobody is forced to use a small model, so that is a weak defence.

**What replaced it.** A narrower claim that does not depend on models being incapable.

Models can reason about this correctly, and they cannot be relied on to do it identically twice, cannot show their work in a mechanically checkable form, and are trained to prefer answering over asking. Abstention is a soft constraint that degrades under long context, adversarial phrasing and edge cases. A rule that fires does not degrade.

The capability gap is closing. The reliability gap is not, because it is not a capability problem.

**What would change it back.** Nothing likely. But this is the claim to keep testing, because it is the one the whole project rests on, and the model baseline in D12 exists partly to keep it honest.

---

## D17. Deleting the record itself

**Proposed.** Nothing was proposed. Each version of the requirements document rewrote the previous one and reduced its reasoning to a few lines in a change record.

**Why it looked right.** It was not a decision so much as a habit. The request early on was for a clean client-facing specification, and that frame kept being applied after it stopped being the only thing needed. A clean specification and a complete record are different artifacts and they were collapsed into one.

There is a less flattering reading, which is that a document showing five reversals looks less authoritative than one showing none. That was not the intention but it was the effect.

**What changed it.** Being asked why so much was being suppressed. It was a fair question and there was no good answer.

**What replaced it.** This file and the discovery log alongside it. The specification stays clean. The reasoning stops being invisible.

**What would change it back.** Nothing. The cost of keeping these is two files. The cost of not keeping them is that every rejected idea gets proposed again by the next person, including an automated one, and the strongest evidence of careful work disappears.
