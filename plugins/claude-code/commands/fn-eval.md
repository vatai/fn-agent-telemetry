---
description: Rate this session on a figure of merit and store it with the telemetry
argument-hint: [what you were judging]
allowed-tools: AskUserQuestion, Bash(${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback:*)
---

Rate the current session. Exactly three questions, asked one at a time.

**1. Work out the subject yourself — do not ask.** In a few words, name what this
session should be judged on: the task the user set, not the tools you used. If
arguments were given, use those verbatim instead: $ARGUMENTS

**2. Q1 — the figure of merit.** Call AskUserQuestion with one question and
nothing else. In the question text, say in a sentence or two what a figure of
merit is — the performance metric that characterises the problem, system or
method being developed with the agent — and say that the next question will ask
for its value. Offer these as options, and say they may name their own instead:

| Option            | Suits                             | Unit      |
| ----------------- | --------------------------------- | --------- |
| `flops`           | numerical algorithms              | GFLOP/s   |
| `samples_per_sec` | ML throughput                     | samples/s |
| `accuracy`        | ML model quality                  | —         |
| `loss`            | ML training loss                  | —         |
| `speedup`         | optimising existing code          | x         |
| `hours_saved`     | human effort spared on development| h         |
| `text_quality`    | text generated for a paper        | 1–5       |
| `plot_quality`    | plots generated for a paper       | 1–5       |

A name they type themselves is fine — this list is a starting point, not a
vocabulary. Ask for the unit with the name if their own figure has one.

**3. Q2 — the value.** Call AskUserQuestion again with one question: the number
they observed for that figure, naming its unit. Offer a few plausible values as
options; they may type their own instead.

**4. Q3 — the session overall, 1–5.** Call AskUserQuestion a third time, one
question, options `1` `2` `3` `4` `5` with 5 labelled best. Explain in the
question text that this is the same figure of merit normalised, so it should
follow from Q1 and Q2: a 100× speedup is a 5, no change is a 3, and a slowdown
is a 1. It is what makes sessions measured in different units comparable, which
is why it is asked rather than worked out from the number.

**5. Record it**, once all three answers are in hand and not before — the
command requires every one of them:

```
"${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback" --subject "<from step 1>" --fom <Q1> --unit "<Q1's unit, if any>" --value <Q2> --satisfaction <Q3>
```

Omit `--unit` for a figure with no unit. If the user volunteered anything the
numbers cannot express, add `--comment "..."`.

**6.** Report the line it prints, then tell the user this, in your own words:
the archive is packed now, but Claude Code writes the session's cost only when
it exits, so close this session for the cost to be recorded — the archive is
repacked then. Do not use any other tools and do not do anything else.

Never put two questions in one AskUserQuestion call. An answer can come back
partial, which forces you to re-ask and makes it look like a fourth question —
and neither Q2 nor Q3 can be worded before the answer it follows.
