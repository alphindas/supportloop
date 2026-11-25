# Retrieval evaluation v1

| Field | Value |
|---|---|
| Generated | 2026-11-25 |
| Git commit | 270a034 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | evals/sets/retrieval_v1.jsonl (0/125 rows human-reviewed) |
| Embedding model | BAAI/bge-small-en-v1.5 |
| Reranker model | BAAI/bge-reranker-v2-m3 |
| Retrieval mode | dense |
| Retrieval device | cuda |
| Corpus fingerprint | 78fdf89e95037eec |
| Generator LLM | none (retrieval only) |
| Judge model | qwen/qwen3.8-27b (configured; not used in this report) |

## Held-out test split

60 questions with an expected article. Recall@5 and MRR count articles, not chunks. 95% bootstrap intervals (10000 resamples, seed 20261125). A zero-width interval does not mean zero uncertainty.

| Setup | Recall@5 | MRR | p50 ms | p95 ms |
|---|---|---|---|---|
| BM25 only | 0.592 [0.475, 0.708] | 0.469 [0.367, 0.571] | 0 | 0 |
| Dense only | 0.850 [0.758, 0.925] | 0.735 [0.644, 0.820] | 16 | 25 |
| Hybrid (RRF) | 0.808 [0.708, 0.892] | 0.673 [0.577, 0.763] | 14 | 23 |
| Dense + reranker **(the app)** | 0.833 [0.742, 0.917] | 0.722 [0.623, 0.813] | 149 | 173 |
| Hybrid + reranker | 0.833 [0.742, 0.917] | 0.725 [0.629, 0.815] | 153 | 181 |

**Paired comparisons on test (first minus second):**

- Dense + reranker minus Hybrid + reranker, Recall@5: +0.000 [-0.050, +0.050] (no clear difference)
- Dense + reranker minus Hybrid + reranker, MRR: -0.003 [-0.013, +0.007] (no clear difference)
- Dense + reranker minus Dense only, Recall@5: -0.017 [-0.100, +0.067] (no clear difference)
- Dense + reranker minus Dense only, MRR: -0.012 [-0.080, +0.053] (no clear difference)

### Decision: is BM25 needed?

Rule (written in `config/benchmark.yaml` before dense + reranker was measured): use dense + reranker if its mean is at most 0.034 below hybrid + reranker on both Recall@5 and MRR, on the test split. Measured gaps: Recall@5 +0.000, MRR -0.003. **Rule result: drop BM25 (dense + reranker).** The app is configured as `dense`.

**Caveat:** this decision was made on the test split. For the choice between these two pipelines, the test numbers are therefore no longer unseen, and a tie is not proof that the two are equal. A check on new questions is needed.

### Same ablation on the dev split (used for model selection)

| Setup | Recall@5 | MRR |
|---|---|---|
| BM25 only | 0.733 [0.567, 0.883] | 0.640 [0.490, 0.782] |
| Dense only | 0.933 [0.833, 1.000] | 0.853 [0.735, 0.953] |
| Hybrid (RRF) | 0.933 [0.833, 1.000] | 0.719 [0.596, 0.834] |
| Dense + reranker | 0.967 [0.900, 1.000] | 0.894 [0.794, 0.967] |
| Hybrid + reranker | 1.000 [1.000, 1.000] | 0.928 [0.856, 0.983] |

The reranked setups score much higher on dev than on the test questions. Dev is small, the models were chosen on it, and the two splits may differ in difficulty. **Quote the test numbers, not the dev numbers.** The only change made in response to test results is the BM25 decision above; no thresholds, weights or text were tuned on test.

### By question type (the app's setup)

| Group | n | Recall@5 | MRR |
|---|---|---|---|
| banking77_eval_pool | 34 | 0.882 [0.765, 0.971] | 0.717 [0.587, 0.840] |
| ai_written | 26 | 0.769 [0.615, 0.904] | 0.729 [0.583, 0.862] |
| single | 50 | 0.840 [0.740, 0.940] | 0.707 [0.596, 0.812] |
| multi | 10 | 0.800 [0.650, 0.950] | 0.800 [0.650, 0.950] |

### Questions where an expected article was missed (test)

- `ret-003` "My account was charged for a withdraw I tried to make that was decline.": expected ['cash-withdrawal-pending'], got ['cash-withdrawal-declined', 'declined-card-payment', 'transfer-failed', 'foreign-payment-wrong-rate', 'cash-withdrawals']
- `ret-007` "I think my card payment has been stopped": expected ['card-payment-reversed'], got ['declined-card-payment', 'lost-or-stolen-card', 'topup-failed', 'unrecognised-card-payment', 'card-payment-pending']
- `ret-015` "How do I transfer funds from my American Express into my account?": expected ['supported-cards-currencies'], got ['topup-by-bank-transfer', 'topup-methods', 'exchange-currency', 'topup-by-card', 'receiving-money']
- `ret-025` "I would like to reactivate my card.": expected ['link-card'], got ['card-expiry', 'activate-card', 'card-not-working', 'card-pin', 'lost-or-stolen-card']
- `ret-058` "the hotel took way more than my room cost and it's still sitting there": expected ['card-payment-pending'], got ['card-acceptance', 'charged-twice', 'refund-not-showing', 'extra-statement-charge', 'cash-wrong-amount']
- `ret-059` "i never got the goods and the seller is ignoring me, can you get my money back": expected ['disputes-chargebacks'], got ['request-refund', 'refund-not-showing', 'transfer-not-received', 'cancel-transfer', 'charged-twice']
- `ret-063` "my new plastic came in the post, now what": expected ['activate-card'], got ['compromised-card', 'card-pin', 'card-delivery-times', 'card-expiry', 'transfer-not-received']
- `ret-065` "how do i pay someone who banks with a different company": expected ['send-money'], got ['topup-by-cash', 'receiving-money', 'topup-by-bank-transfer', 'transfer-fees', 'direct-debit-unrecognised']
- `ret-069` "what does it cost to add money with a credit card and how much can I add per day": expected ['topup-fees', 'topup-limits'], got ['topup-limits', 'cash-withdrawals', 'topup-by-cash', 'topup-verification', 'topup-methods']
- `ret-073` "what rate do you use for euros and is there any fee for exchanging": expected ['exchange-rates', 'exchange-fees'], got ['exchange-fees', 'exchange-currency', 'extra-statement-charge', 'foreign-payment-wrong-rate', 'transfer-fees']
- `ret-076` "do you charge to take cash out abroad and what exchange rate do I get": expected ['cash-withdrawals', 'exchange-rates'], got ['foreign-payment-wrong-rate', 'cash-withdrawals', 'exchange-fees', 'extra-statement-charge', 'exchange-currency']
- `ret-077` "my transfer got declined, is it because you haven't checked where my money is from": expected ['transfer-failed', 'source-of-funds'], got ['transfer-failed', 'beneficiary-not-allowed', 'declined-card-payment', 'send-money', 'transfer-not-received']

## Escalation threshold

Calibrated on **dev** only: the highest top-reranker-score cut-off that wrongly escalates at most 5% of answerable dev questions. Calibrated value: **0.0049**. Value in config: **0.0049**. The table uses the config value. The dev row is optimistic because the value was chosen on it. The threshold is only one safety layer; the model can also choose to escalate.

How fragile the value is: the lowest answerable dev scores are 0.0007, 0.0050, 0.0495, 0.0799. With so few questions, one score can move the threshold a long way.

| Split | Answerable wrongly escalated | Unanswerable banking caught | Off-topic caught |
|---|---|---|---|
| dev | 1/30 (3%) | 7/8 (88%) | 7/7 (100%) |
| test | 5/60 (8%) | 8/10 (80%) | 10/10 (100%) |

## Model selection: embedder and reranker (dev split only)

Source: `make benchmark-retrieval`, run with retrieval mode `dense`. Each row ran in its own process. VRAM is the peak PyTorch reserved while answering queries; the CUDA driver uses some more.

| Embedder | Reranker | Recall@5 | MRR | p50 ms | p95 ms | Peak VRAM MiB |
|---|---|---|---|---|---|---|
| Qwen/Qwen3-Embedding-0.6B | none | 0.933 | 0.878 | 59 | 82 | 1204 |
| Qwen/Qwen3-Embedding-0.6B | Qwen/Qwen3-Reranker-0.6B | 0.967 | 0.834 | 502 | 617 | 2350 |
| Qwen/Qwen3-Embedding-0.6B | BAAI/bge-reranker-v2-m3 | 0.967 | 0.911 | 183 | 213 | 2306 |
| BAAI/bge-m3 | none | 1.000 | 0.872 | 30 | 43 | 1140 |
| BAAI/bge-m3 | Qwen/Qwen3-Reranker-0.6B | 1.000 | 0.841 | 487 | 547 | 2284 |
| BAAI/bge-m3 | BAAI/bge-reranker-v2-m3 | 1.000 | 0.928 | 160 | 181 | 2232 |
| BAAI/bge-small-en-v1.5 | none | 0.933 | 0.853 | 13 | 22 | 106 |
| BAAI/bge-small-en-v1.5 | Qwen/Qwen3-Reranker-0.6B | 0.933 | 0.807 | 468 | 510 | 1246 |
| BAAI/bge-small-en-v1.5 | BAAI/bge-reranker-v2-m3 **(selected)** | 0.967 | 0.894 | 145 | 181 | 1196 |

Selected pair on **CPU**: p50 3902 ms, p95 4854 ms (matters when Ollama needs the GPU).

## Model selection: local LLM

Source: `make benchmark-llm`, 2026-11-25. 30 tasks from the dev split, with context from the retriever above (embedder and reranker released first). 'Pass' means correct behaviour, all code checks passed and, for answers, an expected article cited. It does **not** judge whether the wording is correct. With this few tasks, small gaps are noise.

| Model | Pass | Behaviour correct | Valid JSON | Code checks passed | p50 s | p95 s | Output tok/s | VRAM GiB (share on GPU) |
|---|---|---|---|---|---|---|---|---|
| ollama:qwen3.5:2b | 16/30 | 17/30 | 30/30 | 30/30 | 1.2 | 1.7 | 46 | 2.19 (100%) |
| ollama:llama3.2:3b **(selected)** | 21/30 | 23/30 | 30/30 | 30/30 | 1.5 | 1.8 | 54 | 2.38 (100%) |
| ollama:phi4-mini | 20/30 | 20/30 | 30/30 | 30/30 | 1.8 | 3.2 | 45 | 2.88 (100%) |
| groq:openai/gpt-oss-20b | 26/30 | 28/30 | 30/30 | 30/30 | 0.6 | 1.4 | - | hosted |

Hosted reference is not part of the local choice. Answerable tasks whose expected article was not retrieved: 1.

An earlier run, with the earlier hybrid retrieval, left GPU placement to Ollama (no `num_gpu` setting; saved in `benchmark_llm_auto_offload.json`): qwen3.5:2b 63% on GPU, p50 2.0 s, pass 19/30; llama3.2:3b 80% on GPU, p50 2.0 s, pass 24/30; phi4-mini 74% on GPU, p50 3.8 s, pass 20/30.

**Which mistakes each model made**

| Model | Answered when it should have handed off or refused | Handed off or refused an answerable question | Refused when it should have handed off |
|---|---|---|---|
| ollama:qwen3.5:2b | 0 | 11 | 1 |
| ollama:llama3.2:3b | 3 | 3 | 1 |
| ollama:phi4-mini | 0 | 7 | 3 |
| groq:openai/gpt-oss-20b | 0 | 0 | 2 |

These are the model's raw choices. In the app, the retrieval score threshold and the output checks run afterwards and can turn an answer into a hand-off.

## Limitations

- Articles, the AI-written questions and all labels were drafted by AI. Unless rows are marked human-reviewed above, no person has checked them. Scores are likely optimistic.
- The real Banking77 messages were drawn at random, but three too vague to label were removed, which makes the set a little easier.
- The knowledge base is small (see the article count in `data/kb`), so retrieval is much easier than on a large corpus.
- Model choice used only 30 dev questions, so close candidates cannot be separated.
- Latency is one run on one laptop GPU, one query at a time.
