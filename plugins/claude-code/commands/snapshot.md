---
description: Copy this session's transcript into the telemetry snapshot directory
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-snapshot:*)
---

Transcript snapshot: !`"${CLAUDE_PLUGIN_ROOT}/bin/agent-telemetry-snapshot"`

Report the result of the snapshot above to the user in one line. Do not use any
other tools and do not do anything else.
