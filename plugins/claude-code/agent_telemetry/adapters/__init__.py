"""Per-agent adapters that normalize native hook payloads."""

from . import claude_code

_ADAPTERS = {
    claude_code.AGENT: claude_code,
}


def get_adapter(agent):
    return _ADAPTERS.get(agent)


def known_agents():
    return sorted(_ADAPTERS)
