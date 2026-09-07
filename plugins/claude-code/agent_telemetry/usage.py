"""Token usage and cost, read from each agent's own session record.

Neither number reaches a hook payload under Claude Code -- audited across every
hook type but `PreCompact`, and the only token-shaped fields anywhere are
`SessionStart`'s `context_tokens` and `estimated_cache_write_usd` on a resume,
which are the size of the context and an estimate of re-priming it, not what was
consumed. So the record is read, and nothing of it is kept but the numbers here.

Two rules are load-bearing and easy to get wrong. Claude Code writes one record
per content block and repeats the *whole* message's usage on each, so usage is
summed one per `message.id`; a per-record sum double-counts exactly the messages
that thought or called a tool. And cost appears in a `cost-state` record written
as a session ends, so the largest is taken rather than the last -- a session
resumed after one was written goes on to write another -- with absence meaning
unknown rather than zero.
"""

import json
import os

FIELDS = ("input", "output", "reasoning", "cache_read", "cache_write")


def from_claude_record(path):
    """Usage rows and cost from Claude Code's own transcript. Never copies it."""
    rows, costs, seen = [], [], set()
    for record in _records(path):
        if record.get("type") == "assistant":
            row = _claude_row(record)
            if row and row["message_id"] not in seen:
                seen.add(row["message_id"])
                rows.append(row)
        elif record.get("type") == "cost-state":
            cost = record.get("totalCostUSD")
            if cost is not None:
                costs.append(cost)
    return rows, (max(costs) if costs else None)


def from_opencode_messages(messages):
    """Usage rows and cost from what the opencode SDK returned. Never stores it."""
    rows, cost, any_reply = [], 0.0, False
    for message in messages or []:
        info = (message or {}).get("info") or {}
        if info.get("role") != "assistant":
            continue
        any_reply = True
        cost += info.get("cost") or 0
        tokens = info.get("tokens") or {}
        cache = tokens.get("cache") or {}
        rows.append(
            {
                "message_id": info.get("id"),
                "model": _opencode_model(info),
                "input": tokens.get("input") or 0,
                "output": tokens.get("output") or 0,
                "reasoning": tokens.get("reasoning") or 0,
                "cache_read": cache.get("read") or 0,
                "cache_write": cache.get("write") or 0,
            }
        )
    return rows, (cost if any_reply else None)


def _claude_row(record):
    message = record.get("message") or {}
    if not message.get("id"):
        return None
    usage = message.get("usage") or {}
    details = usage.get("output_tokens_details") or {}
    return {
        "message_id": message.get("id"),
        "model": message.get("model"),
        "input": usage.get("input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
        "reasoning": details.get("thinking_tokens") or 0,
        "cache_read": usage.get("cache_read_input_tokens") or 0,
        "cache_write": usage.get("cache_creation_input_tokens") or 0,
    }


def _opencode_model(info):
    """Provider and model together: the same model id can come from either."""
    return "/".join(p for p in (info.get("providerID"), info.get("modelID")) if p)


def _records(path):
    """Yield the parsed records of a JSONL file, tolerating a half-written line."""
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                yield json.loads(line)
            except ValueError:
                continue
