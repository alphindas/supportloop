# Interview notes: Phase 2 (measure and monitor)

Numbers come from `reports/eval_v1_groq-openai-gpt-oss-20b_prompt-v1.md` and `reports/production_signals_simulation.md`. Written 2026-11-25.

**Be honest about authorship:** the eval tasks, labels, reference answers and judge rubric were drafted by AI with Claude Code.

**Do not call the judge validated.** Human review round 1: 20/30 agreement (67%), 67% expected by chance, kappa -0.01. Round 2 is pending; update these notes with its real numbers when it is done.

## 1. What we built and why

- Every API turn is saved to SQLite, with personal data removed, plus the evidence behind the reply.
- Customers can rate a reply. Weak or risky turns get a "failure signal", which Phase 3 will mine.
- Prometheus metrics show volume, speed, errors, hand-offs, guardrail hits and tokens.
- One OpenTelemetry trace per request shows each stage, with no message text.
- A simulator replayed 200 real customer messages through the running API.
- An eval set of 150 tasks, graded by code rules plus an LLM judge, with confidence intervals.
- A tool to check the judge against a person.
- Why: Phase 3 will change the system. Without this, "better" would be a guess.

## 2. Design decisions and rejected alternatives

| Decision | Why | Rejected, and why |
|---|---|---|
| SQLite through SQLAlchemy | One file, no server, enough for one process. | Postgres: right for many writers; extra setup here. |
| Save after replying; a failed save never fails the chat | The customer matters more than the record. The failure is counted and logged. | Failing the request: monitoring would cause outages. The cost: some turns can be lost. |
| Store the article text shown with each turn | I can explain or re-judge a reply after the articles change. | Chunk IDs only: the text behind them changes. Cost: more storage. |
| Evals call the pipeline, not the API | Test traffic never enters production data or metrics. | Evaluating through the API: pollutes the signals. |
| Intent labels kept outside the database | Phase 3 mining must not see which topics are planted gaps. | Storing intent: mining could "discover" gaps by reading the answer key. |
| One message per simulated user | Later tests treat messages as independent. | Many per user: makes intervals look tighter than they are. |
| No simulated thumbs-down | Invented ratings would look like real signals. | Random feedback: fabricated data. |
| Low-cardinality metric labels | Labelling by user or request ID would create millions of series. | Per-user labels. |
| Trace attributes in one file; no text in spans | The GenAI conventions are still "Development". Text in traces is another copy of customer data. | Opt-in message content. |
| Rules first, LLM judge second | Code is free, exact and repeatable for behaviour, citations, numbers and PII. The judge is only for meaning. | Judging everything with an LLM: costlier and less reliable. |
| Own judge rubric, not RAGAS | I can read, version and test the rubric, and control quota. | RAGAS: more dependencies and more calls per task. |
| One judge call, two verdicts, reason before verdict | Half the requests. | Two calls: more independent, twice the quota. Risk of one verdict colouring the other. |
| Judge from a different model family, temperature 0, cached | Less self-preference; stable results. | Generator judging itself. |
| Human answers before seeing the judge | Seeing the verdict first pulls people towards it. | Showing the verdict and asking "agree?": inflates agreement. |
| Round 2 added, round 1 kept unedited | The rubric was misapplied on some round-1 items. Editing those verdicts after seeing the judge would make agreement meaningless. Round 2 uses 30 other tasks and is reported separately. | Fixing or deleting round-1 verdicts, or pooling the rounds. |
| Round 2 shows the rubric and hides all judge verdicts | The round-1 screen showed only a one-line question, which was a flaw in the tool: the rule "ignore helpfulness when judging faithfulness" was not visible. | Relying on the reviewer to remember the rubric. |
| Report agreement **and** kappa | If most verdicts are "pass", agreement is high even for a lazy judge. | Agreement alone. |
| Cache plus saved first-run latency | A rerun gives a byte-identical report. | Re-timing cached calls: reports cache speed as model speed. |
| Stop the run on quota or outage | A hand-off caused by a rate limit is not the bot's answer. | Grading it: silently wrong results. |
| Bootstrap intervals | Works for rates, precision, recall and percentiles with one simple idea. | Formula per metric: more to get wrong. |

## 3. Trade-offs, weaknesses, and what I would do with more time

**The most important weakness: the judge is unvalidated.** Faithfulness 0.950 and correctness 0.670 depend on it. In human review round 1, agreement was 20/30 (67%). Given that I said "pass" 22 times and the judge 26 times, chance alone predicts 67%, so kappa is -0.01. By verdict type: faithful 14/17, correct 6/13. I found afterwards that I had misapplied the rubric on some items: I mixed up "faithful" with "helpful", and missed omitted key facts such as the 1.5% fee. So round 1 cannot tell me how much of the disagreement is the judge's fault and how much is mine. I left every verdict unedited and added a second round. The judge also has at least one verdict that breaks the rubric: on `v1-035` it called a missing detail "unfaithful".

**What the numbers show:**

- Pass rate 0.680 [0.607, 0.753].
- The weak spot is knowing when it cannot answer: escalation recall 0.633 on 30 tasks. 7 were answered, 4 refused.
- 25 of 48 failures had the right behaviour but were judged incorrect, often for leaving part of the reference out. This may mean short answers (the prompt caps them at 120 words and does not ask for every condition), strict references, a strict judge, or a mix. I have not separated these causes. I did not edit the references or rubric after seeing results.
- On live-style traffic with the local model, 8 of 36 sampled replies were judged unfaithful. Two that I checked against the articles are wrong statements about fees.

Other weaknesses:

- Tasks and labels are AI-drafted; attacks were written by the same author as the rules.
- The eval set found a redaction bug (`cvv 913`). I fixed it before the first run, so the 15/15 PII result is not an independent test.
- The number rule runs inside the app too, so the eval cannot show how often the model invents numbers.
- Intervals cover which tasks were chosen, not model randomness or judge error.
- Metrics reset on restart; one process only; no alerts, migrations or data retention rule.
- Live judging is a manual command, not a scheduled job.
- No multi-turn tasks in the eval set, so follow-up questions are not measured.

With more time: add a second reviewer and worked examples to the rubric, and change the rubric in a new version if agreement stays poor; add multi-turn tasks and attacks written by someone else; run the same eval on the local model; add alerts on hand-off rate and judged faithfulness.

## 4. Eight likely questions, with short answers

**Q1. How do you know your judge is right?**
I don't yet. I ran a blind review of 30 judge decisions: we agreed on 20, which is exactly what chance predicts here (kappa -0.01). I then realised I had misapplied the rubric on some items, partly mixing up "faithful" with "helpful". My review screen had not shown the rubric. I did not edit those verdicts, because changing them after seeing the judge would make the check meaningless. I added a second blind round on 30 different tasks, with the rubric on screen, and report the two separately. Even a good second round would not be clean proof: I saw the judge's reasoning during round 1, I am one reviewer, and 30 items is small. Better: a written rubric with examples, two independent reviewers, and agreement between the humans measured first. (When round 2 is done, add its real numbers.)

**Q2. Why report kappa as well as agreement?**
My own round 1 is the example: 67% agreement sounds acceptable, but chance alone predicts 67%, so kappa is -0.01. Imagine the judge says "pass" to everything and 90% of answers really are good. Agreement is 90%, but the judge has learned nothing. Kappa subtracts the agreement expected by chance, so that judge scores 0. With very few "fail" cases kappa becomes unstable, so I show the full table too.

**Q3. Why not just use thumbs up and down?**
Feedback is rare, and biased towards annoyed or delighted users. A confidently wrong fee may get a thumbs-up, because the customer does not know it is wrong. So I combine signals: hand-offs, weak search, guardrail hits, ratings and sampled judging. None is ground truth; each only chooses what a person should look at.

**Q4. Faithfulness is 95%, yet you found invented fees. Which is true?**
Both, because they measure different things. 95% is `gpt-oss-20b` on the eval set. The invented fees came from `llama3.2:3b` on replayed traffic, where sampled faithfulness was 0.778. Different model and different questions, so the two numbers cannot be compared. It also shows why a single offline score is not enough.

**Q5. Your number check should have caught the invented fee. Why did it not?**
It checks that each amount in the reply exists, with the same currency sign or percent sign, in a cited article. "£10" exists as the minimum top-up, and "1.5%" exists as the credit card fee. The model attached them to the wrong thing. The check catches invented numbers, not misattached ones. Fixing that needs checking each claim against its source sentence, for example with a second model check before replying, which costs latency and quota.

**Q6. Why are reruns identical? Is the cache hiding randomness?**
Model replies and judge verdicts are cached by a hash of the whole request, and latency from the first uncached run is kept. This makes results reproducible and cheap. And yes, it hides run-to-run variation: it freezes one sample. To measure variation I would run several times without the cache and report the spread. The cache is local, so on a new machine the calls run again and numbers may differ. The saved raw results are in git, so the report itself can be rebuilt exactly.

**Q7. What do the confidence intervals tell you, and what do they not?**
They resample the tasks to show how much a score depends on which tasks I picked. With 150 tasks the pass rate is 0.680 with a range of about 0.61 to 0.75, so a few points of difference between two systems means nothing. For comparing systems on the same tasks I will use a paired test, which is more sensitive. The intervals ignore judge errors, bad labels and unrealistic tasks, which may be larger.

**Q8. How do you keep personal data out of your monitoring?**
Redaction is the first step, before search, logs, storage or the LLM. The model's reply and feedback comments are redacted too. Spans carry no message or query text, only IDs, scores and counts; on errors they record the error type, not the message. Tests check the raw database bytes and spans for planted values. Limits: names and addresses are not detected, a PIN written in an unusual way could slip through (an eval task found one such case, now fixed), and the SQLite file is not encrypted.

## 5. Three files to read

1. **`evals/graders/rules.py`** (with `evals/rubrics/judge_v1.txt`): look at `task_passed`. Be able to say exactly what "pass" means, and why some replies need no judge.
2. **`evals/run_eval.py`**: look at `run_task` (why an outage stops the run instead of being graded, and how first-run latency is kept) and `is_temporary`.
3. **`app/chat/recorder.py`** (with `app/storage/signals.py`): look at what is redacted, why a database error is swallowed, and which events count as failures.

Also worth reading: the "Failed tasks" table in the eval report. Pick three failures and be ready to explain them.
