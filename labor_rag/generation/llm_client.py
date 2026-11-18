"""Scoped LLM clients shared by rewrite, rerank, generation and the CLI."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from labor_rag.settings import Settings
from labor_rag.llm_providers import base_url_field, model_field, secret_field

_request_settings = ContextVar("llm_settings", default=None)
_request_client = ContextVar("llm_client", default=None)


class LLMClient:
    """An application-owned resource. Construction does not open a connection."""

    def __init__(self, settings, *, timeout=60):
        self.settings = settings
        self.timeout = timeout
        self._client = None

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

    def complete(self, system, user, max_tokens=1024):
        from labor_rag.generation.usage import record_call
        with record_call(self.settings.LLM_PROVIDER, self.model) as call:
            return self._complete(system, user, max_tokens, call)

    def _complete(self, system, user, max_tokens, call):
        from labor_rag.generation.usage import response_usage
        if not self.model.strip():
            raise ValueError("Chưa chọn model LLM.")
        client = self.client()
        provider = self.settings.LLM_PROVIDER
        if provider == "gemini":
            from google.genai import types
            options = {"system_instruction": system, "max_output_tokens": max_tokens}
            if "2.5-flash" in self.model:
                options["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            response = client.models.generate_content(
                model=self.model, contents=user, config=types.GenerateContentConfig(**options))
            call.update(response_usage(response, provider))
            result = response.text
        elif provider == "anthropic":
            response = client.messages.create(model=self.model, max_tokens=max_tokens,
                system=system, messages=[{"role": "user", "content": user}])
            call.update(response_usage(response, provider))
            result = "".join(block.text for block in response.content if block.type == "text")
        else:
            response = client.chat.completions.create(model=self.model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            call.update(response_usage(response, provider))
            result = response.choices[0].message.content
        if not result or not result.strip():
            raise RuntimeError("LLM chưa trả về nội dung văn bản.")
        return result

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


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    client = _request_client.get()
    if client is not None:
        return client.complete(system, user, max_tokens)
    client = LLMClient(_request_settings.get() or Settings())
    try:
        return client.complete(system, user, max_tokens)
    finally:
        client.close()
