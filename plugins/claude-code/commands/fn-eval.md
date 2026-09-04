---
description: Rate this session on a figure of merit and store it with the telemetry
argument-hint: [what you were judging]
allowed-tools: AskUserQuestion, Bash(${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback:*)
---

Rate the current session. Exactly two questions, asked one at a time.

**1. Work out the subject yourself — do not ask.** In a few words, name what this
session should be judged on: the task the user set, not the tools you used. If
arguments were given, use those verbatim instead: $ARGUMENTS

**2. First question.** Call AskUserQuestion with one question and nothing else —
which figure of merit to judge the session on:

| Option          | Rates                                          | Answer is    |
| --------------- | ---------------------------------------------- | ------------ |
| `satisfaction`  | how good the session was overall               | 1–5          |
| `correctness`   | did the work come out right                    | 1–5          |
| `code_quality`  | readability and fit with the surrounding code  | 1–5          |
| `autonomy`      | how little steering it needed                  | 1–5          |
| `trust`         | confidence in the result without re-checking   | 1–5          |
| `speedup`       | measured walltime vs the previous version      | a ratio, ×   |
| `time_saved`    | minutes saved vs doing it by hand              | minutes      |
| `iterations`    | corrections needed before it was right         | a count      |

**3. Second question, worded for the answer to the first.** Call AskUserQuestion
again with one question:

- Rated 1–5 → offer `1` `2` `3` `4` `5` as the options, 5 labelled best.
- Measured → ask for the number they observed, naming the unit, and offer a few
  plausible values as options. They may type their own instead.

**4. Record it:**

```
"${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback" --subject "<from step 1>" --fom <first answer> --value <second answer>
```

If the user volunteered anything the number cannot express, add `--comment "..."`.

**5.** Report the line it prints. Do not use any other tools and do not do
anything else.

Never put both questions in one AskUserQuestion call. An answer can come back
partial, which forces you to re-ask and makes it look like a third question —
and the second question cannot be worded until the first is answered.
