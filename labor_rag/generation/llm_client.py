"""Scoped LLM clients shared by rewrite, rerank, generation and the CLI."""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar

from labor_rag.settings import Settings
from labor_rag.llm_providers import base_url_field, model_field, secret_field

_request_settings = ContextVar("llm_settings", default=None)
_request_client = ContextVar("llm_client", default=None)

# Extra output headroom for reasoning tokens, added to each call's answer budget.
# "default" keeps the previous request size; providers such as Groq count the
# requested output against per-minute token quotas.
REASONING_ALLOWANCE = {"default": 0, "off": 256, "low": 1024, "medium": 2048, "high": 4096}
_THINK_BLOCK = re.compile(r"<think>.*?(?:</think>|$)\s*", re.S)


class EmptyCompletion(RuntimeError):
    """The model returned no answer text, usually because reasoning used the output limit."""

    def __init__(self, truncated=False):
        self.truncated = truncated
        super().__init__("LLM chưa trả về nội dung văn bản.")


def _status(exc):
    return getattr(exc, "status_code", None) or getattr(exc, "code", None)


def reasoning_request(provider, model, level):
    """Provider parameters for a reasoning level; empty when the model default applies."""
    model = (model or "").lower()
    if provider == "anthropic":
        # Extended thinking is opt-in and needs its own budget contract; not enabled here.
        return {}
    if provider == "gemini":
        if level == "default":
            # Preserve the earlier behaviour for 2.5 Flash, whose thinking can be disabled.
            return {"thinking_budget": 0} if "2.5-flash" in model else {}
        if "gemini-2.5" in model:
            budgets = {"off": 128 if "pro" in model else 0, "low": 1024, "medium": 4096, "high": 8192}
            return {"thinking_budget": budgets[level]}
        return {"thinking_level": {"off": "MINIMAL", "low": "LOW", "medium": "MEDIUM", "high": "HIGH"}[level]}
    if level == "default":
        return {}
    if level == "off":
        # GPT-OSS cannot disable reasoning; "low" is its smallest level.
        return {"reasoning_effort": "low" if "gpt-oss" in model else "none"}
    return {"reasoning_effort": level}


class LLMClient:
    """An application-owned resource. Construction does not open a connection."""

    def __init__(self, settings, *, timeout=60):
        self.settings = settings
        self.timeout = timeout
        self._client = None
        # Set when the model rejected reasoning parameters; later calls omit them.
        self._reasoning_unsupported = False

    @property
    def model(self):
        provider = self.settings.LLM_PROVIDER
        return getattr(self.settings, model_field(provider).upper())

    def client(self):
        if self._client is not None:
            return self._client
        config = self.settings
        provider = config.LLM_PROVIDER
        key = getattr(config, secret_field(provider).upper())
        if provider != "local" and not key:
            raise ValueError("Chưa thiết lập API key cho LLM đã chọn.")
        if provider == "gemini":
            from google import genai
            self._client = genai.Client(api_key=key, http_options={
                "timeout": self.timeout * 1000, "retry_options": {"attempts": 1},
            })
        elif provider == "anthropic":
            from anthropic import Anthropic
            self._client = Anthropic(api_key=key, timeout=self.timeout, max_retries=0)
        else:
            from openai import OpenAI
            options = {"api_key": key or "local-no-auth", "timeout": self.timeout, "max_retries": 0}
            endpoint_field = base_url_field(provider)
            if endpoint_field:
                endpoint = getattr(config, endpoint_field.upper()).strip()
                if not endpoint:
                    raise ValueError("Chưa thiết lập địa chỉ API cho nhà cung cấp đã chọn.")
                options["base_url"] = endpoint
            self._client = OpenAI(**options)
        return self._client

    def complete(self, system, user, max_tokens=1024, reasoning=None):
        """`max_tokens` is the answer budget; `reasoning` overrides the configured level."""
        from labor_rag.generation.usage import record_call
        level = reasoning or self.settings.LLM_REASONING
        with record_call(self.settings.LLM_PROVIDER, self.model) as call:
            return self._complete(system, user, max_tokens, level, call)

    def _complete(self, system, user, max_tokens, level, call):
        if not self.model.strip():
            raise ValueError("Chưa chọn model LLM.")
        client = self.client()
        provider = self.settings.LLM_PROVIDER
        limit = max_tokens + REASONING_ALLOWANCE[level]
        options = {} if self._reasoning_unsupported else reasoning_request(provider, self.model, level)
        try:
            result, truncated = self._request(client, provider, system, user, limit, options, call)
        except Exception as exc:
            # Models without reasoning controls reject the parameter with 400; retry once without it.
            if not options or _status(exc) != 400:
                raise
            self._reasoning_unsupported = True
            result, truncated = self._request(client, provider, system, user, limit, {}, call)
        if provider not in {"gemini", "anthropic"} and result:
            result = _THINK_BLOCK.sub("", result)
        if not result or not result.strip():
            raise EmptyCompletion(truncated)
        return result

    def _request(self, client, provider, system, user, limit, options, call):
        from labor_rag.generation.usage import response_usage
        if provider == "gemini":
            from google.genai import types
            config = {"system_instruction": system, "max_output_tokens": limit}
            if options:
                config["thinking_config"] = types.ThinkingConfig(**options)
            response = client.models.generate_content(
                model=self.model, contents=user, config=types.GenerateContentConfig(**config))
            call.update(response_usage(response, provider))
            reason = str(getattr((response.candidates or [None])[0], "finish_reason", "") or "")
            return response.text, reason.endswith("MAX_TOKENS")
        if provider == "anthropic":
            response = client.messages.create(model=self.model, max_tokens=limit,
                system=system, messages=[{"role": "user", "content": user}])
            call.update(response_usage(response, provider))
            return ("".join(block.text for block in response.content if block.type == "text"),
                    getattr(response, "stop_reason", None) == "max_tokens")
        response = client.chat.completions.create(model=self.model, max_tokens=limit,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], **options)
        call.update(response_usage(response, provider))
        choice = response.choices[0]
        return choice.message.content, getattr(choice, "finish_reason", None) == "length"

    def models(self):
        client = self.client()
        if self.settings.LLM_PROVIDER == "gemini":
            return sorted({m.name.removeprefix("models/") for m in client.models.list()
                if m.name and "generateContent" in (m.supported_actions or [])})
        return sorted({m.id for m in client.models.list() if m.id})

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


@contextmanager
def use_settings(settings, client=None):
    owned = client is None
    client = client or LLMClient(settings)
    settings_token = _request_settings.set(settings)
    client_token = _request_client.set(client)
    try:
        yield
    finally:
        _request_client.reset(client_token)
        _request_settings.reset(settings_token)
        if owned:
            client.close()


def complete(system: str, user: str, max_tokens: int = 1024, reasoning: str | None = None) -> str:
    """Short classification-style calls pass reasoning="off" so thinking cannot use their budget."""
    client = _request_client.get()
    if client is not None:
        return client.complete(system, user, max_tokens, reasoning)
    client = LLMClient(_request_settings.get() or Settings())
    try:
        return client.complete(system, user, max_tokens, reasoning)
    finally:
        client.close()
