## Result in plain words

Notes by Claude Code, **not reviewed by a human**.

- **On messages that were never mined, on the filled topics, "resolved" rose from 5/54 to
  43/54.** On 30 messages from other topics it went from 25/30 to 26/30. This is the better
  evidence, with three cautions: the topics were picked by their intent label, "resolved"
  relies on an unvalidated judge, and faithful does not mean useful.
- **The gain on the mined questions is expected** (9/29 to 17/29 passed): the articles were
  written for them. 12 of the 29 still fail.
- **Other eval v1 tasks got slightly worse:** 4 of 133 stopped passing and none started.
  By the paired bootstrap interval the drop is clear (-0.060 to -0.008); the exact McNemar
  test, with only 4 changed tasks, gives p = 0.125. From reading the four: two answers now
  leave out a step that the judge wants, one cites differently, and one student-account
  question is now refused instead of handed off. Whether the new articles caused each of
  these has not been established.
- **Circularity beyond the mined set:** Claude Code wrote the labels, the articles and the
  reference answers, and the 17 changed eval v1 tasks have references written to match the
  new articles. The articles are invented policy for a fictional company.
- **Mining missed some gaps.** All 10 planted gaps appeared in the traffic, but only 7 had a
  message flagged. A gap answered confidently from a similar article raises no signal.
  `automatic_top_up` was not found and is still open. The disposable-card article came from
  one flagged message whose intent was not a planted gap.
- The mined turns were answered by `llama3.2:3b`; before/after uses `gpt-oss-20b`. Most
  confirmed failures (18 of 29) were model errors or needless hand-offs, which new articles
  do not target. No prompt or retrieval change was made for them in this cycle.
