# Interview notes: Phase 1 (the chatbot)

Numbers come from `reports/`, except the CPU number-format timings, which come from a first benchmark run (later overwritten) and a quick one-off test. Written 2026-11-25.

**Be honest about authorship:** the articles, many questions and all labels were drafted by AI with Claude Code. Do not call them hand-written. Say what you reviewed yourself.

## 1. What we built and why

- A support chatbot API for NovaPay, a made-up payments app: `POST /chat` and `GET /health`.
- 60 help articles are the only thing the bot may answer from. 10 customer topics are left out on purpose, so Phase 3 has real gaps to find.
- Each message is cleaned of personal data, checked for attacks, searched two ways (by words and by meaning), re-ranked, then sent to an LLM with the 4 best chunks.
- The LLM must reply in a fixed JSON shape. Our code then checks it before the customer sees it.
- When anything looks wrong or weak, the bot hands off to a human.
- Models were chosen by measuring them on this machine (4 GB GPU), not from leaderboards.
- Why: in support, a confident wrong answer about money is worse than "let me get a person".

## 2. Design decisions and rejected alternatives

| Decision | Why | Rejected, and why |
|---|---|---|
| Plain Python, no LangChain | I can explain and test every step. | Frameworks: quicker start, hidden behaviour. |
| Split articles at headings; ID is `article#heading` | A section is one idea. IDs stay the same when other sections change. | Fixed-size splitting: cuts sentences; position-based IDs shift after edits. |
| BM25 + dense search, merged with RRF | They fail in different ways. RRF gives each result 1/(60 + position) from each list, so I never compare two unrelated score scales. | Adding the raw scores: needs scaling and weights I would have to tune. |
| `bge-small-en-v1.5` + `bge-reranker-v2-m3` | On dev: Recall@5 1.000, MRR 0.928, 1,196 MiB peak, against about 2,300 MiB for the bigger embedders with the same quality. | Qwen3 embedder (same dev result, more memory). Qwen3 reranker (lower MRR on dev, 0.84 against 0.93, and slower; run with its default instruction and a smaller batch size). |
| `llama3.2:3b` as the local model | Passed 24/30, against 20/30 (`phi4-mini`) and 19/30 (`qwen3.5:2b`). | The others handed off too much. But they never answered when they should not have, and `llama3.2:3b` did twice. |
| `num_gpu: 99` for local models | Ollama's automatic setting left 20-37% of each model on the CPU despite free memory. | Leaving it automatic: slower. |
| `float32` on CPU | My first choice, `bfloat16`, took about 18 s per query in the benchmark because this CPU has no hardware support for it. `float32` took about 4 s. | `bfloat16`: saves RAM but far slower here. |
| LLM returns JSON; code verifies it | Code can check citations and numbers. A prompt alone only asks nicely. | Free text: hard to check. |
| Fixed texts for refusals and hand-offs | The model cannot improvise where it matters. | Model-written refusals. |
| Confidence from the reranker score | Comes from evidence we can inspect. | Asking the LLM how sure it is: not trustworthy without testing. |
| Cache key = hash of the whole request | A changed article changes the prompt, so no stale answer. Original latency is stored. | (model, prompt version, question): would return old answers after the knowledge base changes. |
| Retry on 429, 5xx and timeouts, with backoff and jitter; obey `retry-after` | Free-plan limits are real. A very long `retry-after` means the daily quota is gone, so we stop. | Retrying everything: a bad key or bad request never succeeds. |
| Fake LLM, embedder and reranker in tests | Tests need no key, GPU or downloads. | Real models in tests: slow and flaky. |

## 3. Trade-offs, weaknesses, and what I would do with more time

**The most important weakness: the extra search stages are not proven.** On the 60 held-out questions the full pipeline scored Recall@5 0.833 and dense search alone 0.850. The paired difference is -0.017 with a 95% interval of -0.083 to +0.050, so there is no clear difference. On dev the same pipeline scored 1.000. Every setup scored lower on test than on dev (dense: 0.933 to 0.850; BM25: 0.733 to 0.592), so the test questions seem harder, but the full pipeline fell the most. I have not proven the cause. I did not tune on test.

Other weaknesses:

- Articles, many questions and all labels are AI-drafted and not yet human-reviewed.
- Nothing yet measures whether answers are *correct* (Phase 2).
- The model sometimes refuses a real banking question instead of handing off (savings interest, in the samples).
- The number check cannot catch word numbers or a real number used wrongly. Non-numeric claims are not checked.
- PII rules miss names and addresses. Injection rules are easy to rephrase around.
- No authentication; memory is lost on restart; one retrieval at a time.
- Local-model mode needs retrieval on the CPU (about 4 s per search).

With more time:

1. Review the labels myself and write more dev questions, with the same mix of hard paraphrases as real traffic.
2. On the new dev set only, test dropping BM25, weighting RRF, and sending more chunks to the reranker. Then confirm on fresh test questions, because I have now seen the current ones.
3. Test a prompt change for "refuse or hand off" as the Phase 3 A/B experiment.

## 4. Eight likely questions, with short answers

**Q1. Why this embedding model? Why not the newer Qwen3 one?**
I benchmarked three embedders with three reranker options on 30 dev questions with AI-drafted labels. With the BGE reranker all three embedders tied (Recall@5 1.000, MRR 0.928), and the 33M-parameter model used about half the memory. The rule, written before the run, was: among ties, take the fastest. On a 4 GB GPU the smaller one is the better choice. The dev set has only 30 questions, so "tied" means I cannot separate them, not that they are equal.

**Q2. Why not just use dense search? Why the extra complexity?**
That is a fair challenge, because on held-out questions I could not show that my pipeline beats dense search alone. It looked much better on dev, but that did not carry over. The reranker also has a second job today: its score drives the escalation threshold. RRF scores come only from positions, so they cannot do that job; the dense similarity score might, but I have not tested it. For a real launch I would build a larger dev set, test dense plus reranker without BM25, and remove whatever does not earn its place.

**Q3. How do you know this works?**
Only partly. Measured: retrieval on 60 held-out questions, the threshold on held-out answerable and unanswerable questions, injection false positives on 3,080 real messages, and code behaviour through tests. Not measured: whether answers are correct and faithful, how many attacks get through, and anything with real users. Phase 2 adds an LLM judge and checks the judge against a human.

**Q4. How do you stop the bot from inventing fees?**
Layers. The prompt allows only the given articles. The model must return JSON with article IDs. Code rejects citations that were not retrieved, answers without a citation, and numbers not found in a cited article. A "£7" is not accepted just because the article says "5 to 7 days"; a test caught that bug in my first version. A weak search score also forces a hand-off. This reduces the risk but does not remove it: a wrong non-numeric statement could still pass.

**Q5. How did you pick the escalation threshold? Why is 0.03 so low?**
On dev I took the highest cut-off that wrongly escalates at most 5% of answerable questions: 0.0311. On test it wrongly escalated 7 of 60 (12%, worse than the target) and caught all 20 unanswerable ones. The number looks small because it is a reranker score, not a probability, and it only means something for this reranker. If I change the reranker I must calibrate again. Most of the 20 negatives are far from any article. I expect near-miss topics, like some planted gaps, to be harder, and I have not measured that.

**Q6. What does your prompt-injection defence really protect against?**
Common, obvious phrasings. It wrongly flagged 0 of 3,080 real messages, but I only tested attacks that I wrote, so I do not know its catch rate. The stronger protection is the design: the bot has no tools, cannot touch accounts, has no secrets in its prompt, treats article and user text as data, and its output is checked. A next step would be a labelled attack set and a comparison with a model-based detector.

**Q7. What happens when Groq returns 429, or the GPU fails?**
429, 5xx and timeouts are retried with exponentially growing, randomised waits, using the server's `retry-after` if given. If it asks for longer than 90 seconds, that usually means a daily quota, so we stop. The customer gets a hand-off message, not an error. A retrieval crash does the same. A weakness: a live request can still wait a long time across several retries, so production needs an overall deadline per request.

**Q8. Why is the cache keyed on the whole request? Does caching make your results fake?**
If the key used only the question, then after I added an article the cache would return the old answer, and my before/after comparison would be wrong. Hashing the whole request, including retrieved text, avoids that. The cache is off for live traffic. For evals it gives identical text on rerun and keeps the first real latency. It does hide run-to-run variation of the model: a rerun shows the same sample, not a new one.

## 5. Three files to read

1. **`app/chat/pipeline.py`**: the whole request in order. Look at `handle` (redaction is first, injection stops before the LLM, failures hand off) and `_decide` (when the model's text is shown and when it is replaced).
2. **`app/rag/retriever.py`** (with `app/rag/fusion.py`): look at `retrieve` (BM25, dense, RRF, rerank), the manifest check that refuses a stale index, and `build_index`.
3. **`app/guardrails/output.py`**: look at `check_answer` and `ungrounded_numbers`. Be ready to give one thing it catches and one thing it misses.

Also worth reading: `config/benchmark.yaml`, the selection rules written before the runs.
