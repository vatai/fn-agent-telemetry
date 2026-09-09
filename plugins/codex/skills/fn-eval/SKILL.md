---
name: fn-eval
description: Rate this session on a figure of merit and store it with the telemetry. Only when the user explicitly asks for it by name; never on your own initiative.
---

Rate the current session. Exactly three questions, asked in prose, one at a
time. Wait for each answer before wording the next.

**1. Work out the subject yourself — do not ask.** In a few words, name what this
session should be judged on: the task the user set, not the tools you used. If
the user said what they were judging when they invoked this, use their words
verbatim instead.

**2. Q1 — the figure of merit.** Ask which figure of merit to judge the session
on, and nothing else. Say in a sentence or two what one is — the performance
metric that characterises the problem, system or method being developed with the
agent — and say that the next question will ask for its value. Suggest these:

| Suggestion        | Suits                              | Unit      |
| ----------------- | ---------------------------------- | --------- |
| `flops`           | numerical algorithms               | GFLOP/s   |
| `samples_per_sec` | ML throughput                      | samples/s |
| `accuracy`        | ML model quality                   | —         |
| `loss`            | ML training loss                   | —         |
| `speedup`         | optimising existing code           | x         |
| `hours_saved`     | human effort spared on development | h         |
| `text_quality`    | text generated for a paper         | 1–5       |
| `plot_quality`    | plots generated for a paper        | 1–5       |

Stop and wait for the answer. Any name is accepted — this list is a starting
point, not a vocabulary — so take what they give you. If they name their own
figure and it has a unit, ask for the unit in the same breath.

**3. Q2 — the value.** Ask for the number they observed for that figure, naming
its unit, and nothing else. Stop and wait. The answer must be a number; if it is
not, ask again.

**4. Q3 — the session overall, 1–5.** Ask one question, for a whole number from
1 to 5 with 5 being best. Explain that this is the same figure of merit
normalised, so it should follow from Q1 and Q2: a 100× speedup is a 5, no change
is a 3, and a slowdown is a 1. It is what makes sessions measured in different
units comparable, which is why it is asked rather than worked out from the
number. Stop and wait.

**5. Record it**, once all three answers are in hand and not before — the
command requires every one of them. The executable sits in the checkout this
skill is part of, two directories above this file, so resolve it through this
file's real path rather than typing a path of your own:

```sh
skill=$(readlink -f "<the absolute path of this SKILL.md>")
"$(dirname "$skill")/../../bin/agent-telemetry-feedback" --subject "<from step 1>" --fom <Q1> --unit "<Q1's unit, if any>" --value <Q2> --satisfaction <Q3>
```

Omit `--unit` for a figure with no unit. If the user volunteered anything the
numbers cannot express, add `--comment "..."`.

If the command exits non-zero it rejected an answer: `--value` must be a number
of 0 or more, and `--satisfaction` a whole number from 1 to 5. Re-ask the
question it rejected and run it again. Do not report the error as the result.

**6.** Report the line it prints, then tell the user this, in your own words:
the JSON file is written now and rewritten at the end of every later turn, so
nothing is lost by carrying on; and it will carry no cost, because codex reports
none — the token counts are all there is. Do not use any other tools and do not
do anything else.

Never ask two questions at once. Neither Q2 nor Q3 can be worded before the
answer it follows, and a single reply covering several tends to arrive with one
part missing.
