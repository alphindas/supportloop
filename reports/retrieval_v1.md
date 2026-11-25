# Retrieval evaluation v1

| Field | Value |
|---|---|
| Generated | 2026-11-25 |
| Git commit | 4a45b37 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | evals/sets/retrieval_v1.jsonl (0/125 rows human-reviewed) |
| Embedding model | BAAI/bge-small-en-v1.5 |
| Reranker model | BAAI/bge-reranker-v2-m3 |
| Retrieval device | cuda |
| Corpus fingerprint | 78fdf89e95037eec |
| Generator LLM | none (retrieval only) |
| Judge model | qwen/qwen3.8-27b (configured; not used in this report) |

## Held-out test split

60 questions with an expected article. Recall@5 and MRR count articles, not chunks. 95% bootstrap intervals (10000 resamples, seed 20261125). A zero-width interval does not mean zero uncertainty.

| Setup | Recall@5 | MRR | p50 ms | p95 ms |
|---|---|---|---|---|
| BM25 only | 0.592 [0.475, 0.708] | 0.469 [0.367, 0.571] | 0 | 0 |
| Dense only | 0.850 [0.758, 0.925] | 0.735 [0.644, 0.820] | 17 | 26 |
| Hybrid (RRF) | 0.808 [0.708, 0.892] | 0.673 [0.577, 0.763] | 17 | 23 |
| Hybrid + reranker (the app) | 0.833 [0.742, 0.917] | 0.725 [0.629, 0.815] | 146 | 170 |

**Paired comparison, app minus dense-only (test):**

- Recall@5: -0.017 [-0.083, +0.050] (no clear difference)
- MRR: -0.009 [-0.076, +0.056] (no clear difference)

### Same ablation on the dev split (used for model selection)

| Setup | Recall@5 | MRR |
|---|---|---|
| BM25 only | 0.733 [0.567, 0.883] | 0.640 [0.490, 0.782] |
| Dense only | 0.933 [0.833, 1.000] | 0.853 [0.735, 0.953] |
| Hybrid (RRF) | 0.933 [0.833, 1.000] | 0.719 [0.596, 0.834] |
| Hybrid + reranker (the app) | 1.000 [1.000, 1.000] | 0.928 [0.856, 0.983] |

Compare the two tables: the chosen setup scores much higher on dev than on the held-out test questions. Dev is small, the models were chosen on it, and the two splits may differ in difficulty. **Quote the test numbers, not the dev numbers.** Nothing in the system has been changed in response to the test results.

### By question type (the app's setup)

| Group | n | Recall@5 | MRR |
|---|---|---|---|
| banking77_eval_pool | 34 | 0.882 [0.765, 0.971] | 0.713 [0.581, 0.839] |
| ai_written | 26 | 0.769 [0.615, 0.904] | 0.742 [0.605, 0.866] |
| single | 50 | 0.840 [0.740, 0.940] | 0.711 [0.602, 0.815] |
| multi | 10 | 0.800 [0.650, 0.950] | 0.800 [0.650, 0.950] |

### Questions where an expected article was missed (test)

- `ret-001` "I have a payment listed in error.": expected ['unrecognised-card-payment'], got ['cash-wrong-amount', 'card-payment-reversed', 'card-payment-pending', 'request-refund', 'declined-card-payment']
- `ret-003` "My account was charged for a withdraw I tried to make that was decline.": expected ['cash-withdrawal-pending'], got ['cash-withdrawal-declined', 'declined-card-payment', 'transfer-failed', 'foreign-payment-wrong-rate', 'cash-withdrawal-unrecognised']
- `ret-015` "How do I transfer funds from my American Express into my account?": expected ['supported-cards-currencies'], got ['topup-by-bank-transfer', 'topup-methods', 'exchange-currency', 'receiving-money', 'bank-transfer-missing']
- `ret-025` "I would like to reactivate my card.": expected ['link-card'], got ['card-expiry', 'activate-card', 'card-not-working', 'lost-or-stolen-card', 'virtual-card']
- `ret-058` "the hotel took way more than my room cost and it's still sitting there": expected ['card-payment-pending'], got ['card-acceptance', 'charged-twice', 'verification-problems', 'refund-not-showing', 'extra-statement-charge']
- `ret-059` "i never got the goods and the seller is ignoring me, can you get my money back": expected ['disputes-chargebacks'], got ['request-refund', 'direct-debit-unrecognised', 'cash-withdrawal-pending', 'exchange-currency', 'transfer-not-received']
- `ret-063` "my new plastic came in the post, now what": expected ['activate-card'], got ['card-expiry', 'compromised-card', 'card-pin', 'topup-by-cash', 'card-delivery-times']
- `ret-065` "how do i pay someone who banks with a different company": expected ['send-money'], got ['topup-by-cash', 'receiving-money', 'topup-by-bank-transfer', 'transfer-fees', 'direct-debit-unrecognised']
- `ret-069` "what does it cost to add money with a credit card and how much can I add per day": expected ['topup-fees', 'topup-limits'], got ['topup-limits', 'cash-withdrawals', 'topup-by-cash', 'topup-verification', 'topup-methods']
- `ret-072` "can I get a virtual card now while I wait for the real one, and when will that arrive": expected ['virtual-card', 'card-delivery-times'], got ['order-physical-card', 'virtual-card', 'topup-by-card', 'topup-reverted', 'card-expiry']
- `ret-073` "what rate do you use for euros and is there any fee for exchanging": expected ['exchange-rates', 'exchange-fees'], got ['exchange-fees', 'exchange-currency', 'extra-statement-charge', 'foreign-payment-wrong-rate', 'transfer-fees']
- `ret-076` "do you charge to take cash out abroad and what exchange rate do I get": expected ['cash-withdrawals', 'exchange-rates'], got ['foreign-payment-wrong-rate', 'cash-withdrawals', 'extra-statement-charge', 'exchange-fees', 'exchange-currency']

## Escalation threshold

Calibrated on **dev** only: the highest top-reranker-score cut-off that wrongly escalates at most 5% of answerable dev questions. Calibrated value: **0.0311**. Value in config: **0.0311**. The table uses the config value. The dev row is optimistic because the value was chosen on it. The threshold is only one safety layer; the model can also choose to escalate.

| Split | Answerable wrongly escalated | Unanswerable banking caught | Off-topic caught |
|---|---|---|---|
| dev | 2/30 (7%) | 8/8 (100%) | 7/7 (100%) |
| test | 7/60 (12%) | 10/10 (100%) | 10/10 (100%) |

## Model selection: embedder and reranker (dev split only)

Source: `make benchmark-retrieval`. Each row ran in its own process. VRAM is the peak PyTorch reserved while answering queries; the CUDA driver uses some more.

| Embedder | Reranker | Recall@5 | MRR | p50 ms | p95 ms | Peak VRAM MiB |
|---|---|---|---|---|---|---|
| Qwen/Qwen3-Embedding-0.6B | none | 0.967 | 0.766 | 51 | 61 | 1204 |
| Qwen/Qwen3-Embedding-0.6B | Qwen/Qwen3-Reranker-0.6B | 0.967 | 0.842 | 480 | 520 | 2350 |
| Qwen/Qwen3-Embedding-0.6B | BAAI/bge-reranker-v2-m3 | 1.000 | 0.928 | 181 | 212 | 2306 |
| BAAI/bge-m3 | none | 0.967 | 0.754 | 24 | 36 | 1140 |
| BAAI/bge-m3 | Qwen/Qwen3-Reranker-0.6B | 0.967 | 0.840 | 450 | 487 | 2284 |
| BAAI/bge-m3 | BAAI/bge-reranker-v2-m3 | 1.000 | 0.928 | 154 | 176 | 2232 |
| BAAI/bge-small-en-v1.5 | none | 0.933 | 0.719 | 14 | 21 | 106 |
| BAAI/bge-small-en-v1.5 | Qwen/Qwen3-Reranker-0.6B | 1.000 | 0.843 | 442 | 489 | 1246 |
| BAAI/bge-small-en-v1.5 | BAAI/bge-reranker-v2-m3 **(selected)** | 1.000 | 0.928 | 138 | 170 | 1196 |

Selected pair on **CPU**: p50 4055 ms, p95 4830 ms (matters when Ollama needs the GPU).

## Model selection: local LLM

Source: `make benchmark-llm`, 2026-11-25. 30 tasks from the dev split, with context from the retriever above (embedder and reranker released first). 'Pass' means correct behaviour, all code checks passed and, for answers, an expected article cited. It does **not** judge whether the wording is correct. With this few tasks, small gaps are noise.

| Model | Pass | Behaviour correct | Valid JSON | Code checks passed | p50 s | p95 s | Output tok/s | VRAM GiB (share on GPU) |
|---|---|---|---|---|---|---|---|---|
| ollama:qwen3.5:2b | 19/30 | 20/30 | 30/30 | 30/30 | 1.2 | 1.7 | 45 | 2.19 (100%) |
| ollama:llama3.2:3b **(selected)** | 24/30 | 24/30 | 30/30 | 30/30 | 1.5 | 1.8 | 55 | 2.38 (100%) |
| ollama:phi4-mini | 20/30 | 20/30 | 30/30 | 30/30 | 1.7 | 2.9 | 47 | 2.88 (100%) |
| groq:openai/gpt-oss-20b | 27/30 | 28/30 | 30/30 | 30/30 | 0.6 | 1.3 | - | hosted |

Hosted reference is not part of the local choice. Answerable tasks whose expected article was not retrieved: 0.

An earlier run left GPU placement to Ollama (no `num_gpu` setting; saved in `benchmark_llm_auto_offload.json`): qwen3.5:2b 63% on GPU, p50 2.0 s, pass 19/30; llama3.2:3b 80% on GPU, p50 2.0 s, pass 24/30; phi4-mini 74% on GPU, p50 3.8 s, pass 20/30.

**Which mistakes each model made**

| Model | Answered when it should have handed off or refused | Handed off or refused an answerable question | Refused when it should have handed off |
|---|---|---|---|
| ollama:qwen3.5:2b | 0 | 9 | 1 |
| ollama:llama3.2:3b | 2 | 3 | 1 |
| ollama:phi4-mini | 0 | 7 | 3 |
| groq:openai/gpt-oss-20b | 0 | 0 | 2 |

These are the model's raw choices. In the app, the retrieval score threshold and the output checks run afterwards and can turn an answer into a hand-off.

## Limitations

- Articles, the AI-written questions and all labels were drafted by AI. Unless rows are marked human-reviewed above, no person has checked them. Scores are likely optimistic.
- The real Banking77 messages were drawn at random, but three too vague to label were removed, which makes the set a little easier.
- The knowledge base is small (see the article count in `data/kb`), so retrieval is much easier than on a large corpus.
- Model choice used only 30 dev questions, so close candidates cannot be separated.
- Latency is one run on one laptop GPU, one query at a time.
