"""Per-agent adapters that normalize native hook payloads."""

from . import claude_code, opencode

_ADAPTERS = {
    claude_code.AGENT: claude_code,
    opencode.AGENT: opencode,
}


def get_adapter(agent):
    return _ADAPTERS.get(agent)


def known_agents():
    return sorted(_ADAPTERS)
