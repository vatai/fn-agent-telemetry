---
description: Rate this session on a figure of merit and store it with the telemetry
---

Rate the current session. Exactly two questions, asked one at a time.

**1. Work out the subject yourself — do not ask.** In a few words, name what this
session should be judged on: the task the user set, not the tools you used. If
arguments were given, use those verbatim instead: $ARGUMENTS

**2. First question.** Ask which figure of merit to judge the session on, and
nothing else. Offer exactly these, and accept only one of these names:

| Answer          | Rates                                          | Value is     |
| --------------- | ---------------------------------------------- | ------------ |
| `satisfaction`  | how good the session was overall               | 1–5          |
| `correctness`   | did the work come out right                    | 1–5          |
| `code_quality`  | readability and fit with the surrounding code  | 1–5          |
| `autonomy`      | how little steering it needed                  | 1–5          |
| `trust`         | confidence in the result without re-checking   | 1–5          |
| `speedup`       | measured walltime vs the previous version      | a ratio, ×   |
| `time_saved`    | minutes saved vs doing it by hand              | minutes      |
| `iterations`    | corrections needed before it was right         | a count      |

Stop and wait for the answer. If it is not one of the eight names, ask again.

**3. Second question, worded for the answer to the first.** Ask for the value,
and nothing else:

- Rated 1–5 → ask for a whole number from 1 to 5, 5 being best.
- Measured → ask for the number they observed, naming the unit.

Stop and wait. The answer must be a number; if it is not, ask again.

**4. Record it:**

```
"$AGENT_TELEMETRY_BIN/agent-telemetry-feedback" --subject "<from step 1>" --fom <first answer> --value <second answer>
```

If the user volunteered anything the number cannot express, add `--comment "..."`.

If the command exits non-zero it rejected the value against the figure's own
scale: re-ask the second question and run it again. Do not report the error as
the result.

**5.** Report the line it prints. Do not use any other tools and do not do
anything else.

Never ask both questions at once. The second cannot be worded until the first is
answered, and a single reply covering both tends to arrive with one half missing.
