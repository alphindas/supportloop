# A/B test: prompt v1 against prompt v2

| Field | Value |
|---|---|
| Generated | 2026-11-27 |
| Git commit | 6226cc3 |
| Config | config/settings.yaml |
| Prompt version | v1 |
| Eval set | evals/sets/v2.jsonl and the Banking77 A/B pool |
| Offline generator | openai/gpt-oss-20b |
| Online generator | ollama:phi4-mini |
| Experiment file SHA-256 | 31f592c55032f8bfe7bc51f62b3aa88b5fe3916721ec60710733232aa96e5720 |
| Judge model | qwen/qwen3.8-27b (used in this report) |


## Decision: **no decision yet**

- Offline and online results are both needed.

Decision rule applied by code (`ab/analyze.py`). Decisions and notes are by Claude Code, **not reviewed by a human**. The offline pass rate depends on a judge that is not validated.

## Notes on this run

Written by Claude Code (**not reviewed by a human**) after the online traffic had been sent
and while the offline v2 run was still incomplete. At that point no per-variant result,
online or offline, had been looked at. The only number seen was the simulator's total for
both arms together (600 replies: 323 answered, 273 handed off, 4 refused).

- **Order of events.** The experiment file was committed before eval set v2 had been run with
  either prompt. The v1 run on eval set v2 (the offline control) finished before the v2 run.
- **Interruptions.** The offline v2 run stopped more than once on Groq rate limits and was
  resumed. Tasks that hit a limit are not graded; they run again on resume. The knowledge
  base, prompts and retrieval settings were not changed in between.
- **Different settings online and offline.** Online uses `phi4-mini` with retrieval on the
  CPU; offline uses `gpt-oss-20b` on Groq with retrieval on the GPU. They test the same
  prompt change on two models, so they can disagree.
- **The online label is crude.** It comes from the Banking77 intent: "hand off" for the one
  topic with no article, otherwise "answer". It does not check whether an answer is right.
  Some messages under a covered intent cannot be answered from the article, so a correct
  hand-off can be counted as wrong.
- **Online traffic is simulated.** The messages are real Banking77 text, but the users are
  not, and nobody reacted to the replies.
- **Prompt v2 was written knowing the main weakness** found in earlier runs (refusing where
  a hand-off was needed, and wrong fee claims). Eval set v2 contains the eval v1 tasks, so
  its offline result is not a test on unseen weaknesses.

## Added after seeing the online result (exploratory, not pre-registered)

Written by Claude Code, **not reviewed by a human**. These counts come from the stored turns
in the local database, which is not in git.

- The extra hand-offs in the treatment arm were mostly the model's own choice: reason
  `model_chose_escalate` on 171 of 315 treatment replies and 86 of 285 control replies. A
  reply can have more than one reason.
- Code checks blocked few replies in either arm. Number check: 6 control, 1 treatment. Claim
  check: 1 control, 0 treatment. These checks only see replies the model chose to send.
- Mean tokens rose mainly on the input side (about 559 to 718), as expected from a longer
  prompt. Output stayed near 100.
- A likely cause is the new line "If you are unsure between escalate and refuse, choose
  escalate", with `phi4-mini` applying it to answers as well. **This has not been tested.**
  Prompt v2 changed two things at once, so this experiment cannot say which one did it.
- Do not edit prompt v2 and rerun on the same traffic to get a better number. A new prompt
  needs a new version, a new experiment file and fresh messages.

## Offline: paired comparison on eval set v2 (Groq)

**Not complete: 121/179 tasks graded under both prompts.**

## Online: simulated traffic through the live API (phi4-mini)

600 messages, one per simulated user. Split: {'control': 285, 'treatment': 315}. Sample ratio chi-square 1.50: passes. System errors: 0.

| Metric | Control (v1) | Treatment (v2) |
|---|---|---|
| **Behaviour accuracy (primary)** | 183/285 = 0.642 [0.585, 0.696] | 145/315 = 0.460 [0.406, 0.516] |
| Refusal rate (any refusal is wrong) | 4/285 = 0.014 [0.005, 0.036] | 0/315 = 0.000 [0.000, 0.012] |
| Escalation rate | 102/285 = 0.358 [0.304, 0.415] | 174/315 = 0.552 [0.497, 0.606] |
| Latency p95 | 8269 ms | 8259 ms |
| Mean tokens per message | 656 | 819 |

- Behaviour accuracy, v2 minus v1: -0.182 [-0.260, -0.103], two-proportion p < 0.001.
- Guardrails broken: escalation_rate, mean_total_tokens.
