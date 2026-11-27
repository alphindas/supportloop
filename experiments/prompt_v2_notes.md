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
