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

Codex differs again: it writes the session's *cumulative* counts on every
`token_count` event, so a row is what they grew by, and a repeated snapshot
adds nothing. It reports no cost anywhere, so a codex session's cost is
unknown -- its `rate_limits` are what a plan has left, not what a session
spent.
"""

from . import jsonl

FIELDS = ("input", "output", "reasoning", "cache_read", "cache_write")

# Codex reports usage in an event of its own rather than on a message.
CODEX_USAGE_EVENT = "token_count"


def from_claude_record(path):
    """Usage rows and cost from Claude Code's own transcript. Never copies it."""
    rows, costs, seen = [], [], set()
    for record in jsonl.records(path):
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


def from_codex_record(path):
    """Usage rows from codex's own rollout, and no cost: codex reports none.

    A `token_count` event carries the whole session's usage so far, which is why
    a row is the increase over the event before it. That also drops the repeated
    snapshot an aborted turn writes, the same double count summing Claude Code's
    per-block records would produce.
    """
    rows, previous, model = [], None, None
    for record in jsonl.records(path):
        payload = record.get("payload") or {}
        if record.get("type") == "turn_context":
            model = payload.get("model") or model
            continue
        if payload.get("type") != CODEX_USAGE_EVENT:
            continue
        totals = _codex_totals(payload)
        if totals is None:
            continue
        row = _codex_row(totals, previous, model)
        previous = totals
        if row:
            rows.append(row)
    return rows, None


def _codex_totals(payload):
    """Codex's cumulative counts, in this document's own fields.

    `input_tokens` is everything that was sent, cached tokens included, so both
    cached kinds come out of it: a reader adds `input`, `cache_read` and
    `cache_write` together. Verified over every rollout on this machine --
    `input + output` was the reported total on all 1506 snapshots. Freshly
    written cache was 0 in every one of them, so it is assumed to sit inside
    `input_tokens` the way the cached tokens demonstrably do.
    """
    counts = ((payload.get("info") or {}).get("total_token_usage")) or {}
    if not counts:
        return None
    cached = counts.get("cached_input_tokens") or 0
    written = counts.get("cache_write_input_tokens") or 0
    return {
        "input": (counts.get("input_tokens") or 0) - cached - written,
        "output": counts.get("output_tokens") or 0,
        "reasoning": counts.get("reasoning_output_tokens") or 0,
        "cache_read": cached,
        "cache_write": written,
    }


def _codex_row(totals, previous, model):
    """One model request's usage: what the cumulative counts grew by.

    None when nothing grew, which is a snapshot written twice. Codex attributes
    no id to a snapshot, so a codex row has no `message_id`; it is one model
    request rather than one message. The counts only ever climbed in every
    rollout read, and the clamp is there so that a reset could not report a
    negative number of tokens.
    """
    grew = {field: max(0, totals[field] - (previous or {}).get(field, 0)) for field in FIELDS}
    if not any(grew.values()):
        return None
    return {"message_id": None, "model": model} | grew


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

