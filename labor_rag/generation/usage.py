"""Request-local LLM usage, based only on counts reported by providers."""
from contextlib import contextmanager
from contextvars import ContextVar
import re


STAGES = ("session_title", "intent", "query_rewrite", "retrieval", "rerank",
          "appendices", "generation", "verification")
_collector = ContextVar("llm_usage_collector", default=None)
_stage = ContextVar("llm_usage_stage", default="other")


def value(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def count(obj, name):
    result = value(obj, name)
    return result if type(result) is int and result >= 0 else None


def response_usage(response, provider):
    usage = value(response, "usage_metadata" if provider == "gemini" else "usage")
    cached = reasoning = None
    if provider == "gemini":
        incoming = count(usage, "prompt_token_count")
        outgoing = count(usage, "candidates_token_count")
        total = count(usage, "total_token_count")
        reasoning = count(usage, "thoughts_token_count")
        cached = count(usage, "cached_content_token_count")
        if incoming is not None and total is not None and total >= incoming:
            outgoing = total - incoming
        elif outgoing is not None:
            outgoing += reasoning or 0
    elif provider == "anthropic":
        incoming, outgoing = count(usage, "input_tokens"), count(usage, "output_tokens")
        cached = count(usage, "cache_read_input_tokens")
        if incoming is not None:
            incoming += (cached or 0) + (count(usage, "cache_creation_input_tokens") or 0)
        total = None
    else:
        incoming, outgoing = count(usage, "prompt_tokens"), count(usage, "completion_tokens")
        total = count(usage, "total_tokens")
        cached = count(value(usage, "prompt_tokens_details"), "cached_tokens")
        reasoning = count(value(usage, "completion_tokens_details"), "reasoning_tokens")
    if total is None and incoming is not None and outgoing is not None:
        total = incoming + outgoing
    return {"input_tokens": incoming, "output_tokens": outgoing, "total_tokens": total,
            "cached_input_tokens": cached, "reasoning_tokens": reasoning}


class UsageCollector:
    def __init__(self):
        self.calls = []
        self.executed_stages = set()

    def snapshot(self):
        fields = ("input_tokens", "output_tokens", "total_tokens")
        complete = all(all(call.get(field) is not None for field in fields) for call in self.calls)
        any_known = any(call.get(field) is not None for call in self.calls for field in fields)
        totals = {}
        for field in fields:
            known = [call[field] for call in self.calls if call.get(field) is not None]
            totals[field] = sum(known) if known or not self.calls else None
        return {"status": "complete" if complete else "partial" if any_known else "unavailable",
                **totals, "calls": [dict(call) for call in self.calls],
                "executed_stages": [s for s in (*STAGES, "other") if s in self.executed_stages]}


@contextmanager
def collect_usage(*, reuse=False):
    existing = _collector.get()
    if reuse and existing is not None:
        yield existing
        return
    collector = UsageCollector()
    token = _collector.set(collector)
    try:
        yield collector
    finally:
        _collector.reset(token)


@contextmanager
def usage_stage(stage):
    collector = _collector.get()
    if collector is not None:
        collector.executed_stages.add(stage)
    token = _stage.set(stage)
    try:
        yield
    finally:
        _stage.reset(token)


@contextmanager
def record_call(provider, model):
    call = {"stage": _stage.get(), "provider": provider, "model": model, "status": "succeeded",
            **response_usage(None, provider), "error_type": None, "http_status": None,
            "requested_tokens": None}
    try:
        yield call
    except Exception as exc:
        call["status"], call["error_type"] = "failed", type(exc).__name__
        status = getattr(exc, "status_code", None)
        call["http_status"] = status if type(status) is int else None
        # A rejection's requested count is not completed/billable usage. Never
        # store the SDK's raw message: it can contain prompts, keys or URLs.
        if provider == "groq" and status in {413, 429}:
            match = re.search(r"\bRequested\s*:?\s*(\d[\d,]*)", str(exc), re.IGNORECASE)
            if match:
                call["requested_tokens"] = int(match[1].replace(",", ""))
        raise
    finally:
        collector = _collector.get()
        if collector is not None:
            collector.executed_stages.add(call["stage"])
            collector.calls.append(call)
