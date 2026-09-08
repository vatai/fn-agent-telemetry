# fn-agent-telemetry

This plugin provides the `/fn-eval` command your coding agent, to help collect
evaluate agents. The command invocation asks you 3 questions:

- **Q1**: Specifying the problem/FOM (Figure of Merit; see
  [explanation](#fom-figure-of-merit)) of the problem (select one or add a
  custom one);
- **Q2**: FOM as a numerical value;
- **Q3**: Overall satisfaction with the agent/LLM (1-5 scores);

Then it generates one JSON file in `$HOME/agent-telemetry` which should be
uploaded to the URL which is provided separately. It is plain text — read it
before you send it.

It holds six things and nothing else:

- the **skills** that were available to the session, and the text defining them;
- the **tokens** used, per reply;
- what the session **cost**;
- the **`AGENTS.md` and `CLAUDE.md`** files the agent was working under, in full;
- which **tools** ran and how many times each — the tool's name and a count,
  and for a skill the skill's name, so a session records which skills it used
  and not only which it had;
- your **three answers** above.

It does not contain your prompts, the agent's replies, what any tool was given
or returned, or any copy of the conversation. Of tool activity it keeps names
and counts only: no command, no file, no argument, no result.

Typically you'd invoke `/fn-eval` when finished with the session (and for
technical reasons, you actually need to exit `claude` for the cost to be
recorded).

## Install

### Claude Code

```sh
claude plugin marketplace add https://github.com/vatai/fn-agent-telemetry.git
claude plugin install fn-claude-telemetry@fn-agent-telemetry

# To update later (restart Claude Code to apply):
claude plugin marketplace update fn-agent-telemetry
claude plugin update fn-claude-telemetry@fn-agent-telemetry
```

Restart Claude Code, then check with `claude plugin details fn-claude-telemetry`
(9 hooks, 1 command). Uninstall with
`claude plugin uninstall fn-claude-telemetry@fn-agent-telemetry`.

### opencode

Clone the repo and write opencode's config to point at the plugin inside it:

```sh
git clone https://github.com/vatai/fn-agent-telemetry.git ~/.local/share/fn-agent-telemetry
mkdir -p ~/.config/opencode
cat > ~/.config/opencode/opencode.json <<EOF
{
  "plugin": ["$HOME/.local/share/fn-agent-telemetry/plugins/opencode/plugin/agent-telemetry.js"]
}
EOF

# To update later (restart opencode to apply):
git -C ~/.local/share/fn-agent-telemetry pull
```

Restart opencode; `/fn-eval` should appear in the command list.

That `cat` overwrites `~/.config/opencode/opencode.json` — if you already have
one, add the `plugin` entry to it by hand instead.

## FOM: Figure of merit

FOM is a performance metric that characterises the performance of a problem, system or method, which is being developed with the coding agent. Examples could be:

- FLOPs for numerical algorithms,
- samples per sec, accuracy or loss for ML algorithms,
- speedup (e.g., "6.7x") for optimising existing code,
- human hours saved for code development,
- quality/rating of text generated for paper writing,
- quality/rating of generated plots for papers,
- etc.

The `/fn-eval` first asks you to specify which FOM you want to report, and you
can either choose from the suggestions or specify your own FOM; then it asks you
to enter the FOM as a numerical value.
