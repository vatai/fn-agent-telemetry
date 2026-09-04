---
description: Rate this session on a figure of merit and store it with the telemetry
argument-hint: [what you were judging]
allowed-tools: AskUserQuestion, Bash(${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback:*)
---

Collect one rating of the current session, then record it. Two questions, no more.

1. In a few words, name what this session should be judged on — the task the user
   set, not the tools you used. If arguments were given, use those instead: $ARGUMENTS
2. Call AskUserQuestion once, with both questions:
   - **Figure of merit** — which dimension to judge it on: `correctness`,
     `time_saved`, `few_iterations`, `code_quality`, `autonomy`, `trust`.
   - **Score** — 1 to 5, where 5 is best.
3. Run, substituting the answers:
   `"${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-feedback" --subject "<from step 1>" --fom <choice> --value <score>`
4. Report the line it prints. Do not use any other tools and do not do anything else.

If the user volunteers anything the score cannot express, pass it as `--comment "..."`.
