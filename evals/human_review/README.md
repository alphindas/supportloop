# Judge review verdicts

**The judge is not validated by a human yet.**

The folder name and the `human` field come from the original plan, which was a human
review. In each record, `judge` is the eval judge's verdict and `human` is the reviewer's
verdict, **whoever the reviewer was**:

| File ends in | Round | Reviewer |
|---|---|---|
| `.jsonl` | 1 | second-AI reviewer (ChatGPT), **not a person** |
| `.round2.jsonl` | 2 | second-AI reviewer (ChatGPT), **not a person** |
| `.round3.jsonl` (once started) | 3 | meant for a person; each record stores the reviewer's own declaration, which cannot be verified |

Verdict files are never edited. Tests pin rounds 1 and 2 by hash.
See the judge review section of the eval report in `reports/` for what these numbers can
and cannot show.
