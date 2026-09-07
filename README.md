# fn-agent-telemetry

This plugin provides the `/fn-eval` command your coding agent, to help collect
evaluate agents. The command invocation asks you 3 questions:

- **Q1**: Specifying the problem/FOM (Figure of Merit; see
  [explanation](#fom-figure-of-merit)) of the problem (select one or add a
  custom one);
- **Q2**: FOM as a numerical value;
- **Q3**: Overall satisfaction with the agent/LLM (1-5 scores);

Then it generates a zip file in `$HOME/agent-telemetry` which should be uploaded
to the URL which is provided separately.

The `/fn-eval` command collects the agent-user interaction (and almost the
complete log) from the beginning of the session until the `/fn-eval` is invoked.
Typically you'd invoke `/fn-eval` when finished with the session (and for
technical reasons, you actually need to exit `claude` to create a complete zip
file).

## Install

### Claude Code

```sh
claude plugin marketplace add https://github.com/vatai/fn-agent-telemetry.git
claude plugin install fn-claude-telemetry@fn-agent-telemetry
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
