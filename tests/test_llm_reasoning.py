"""Reasoning levels map to provider parameters; no cloud calls."""
from types import SimpleNamespace

import pytest

from labor_rag.generation.llm_client import EmptyCompletion, LLMClient, reasoning_request
from labor_rag.settings import Settings
from src.backend.app.services import configuration


@pytest.mark.parametrize("provider,model,level,expected", [
    ("groq", "openai/gpt-oss-20b", "off", {"reasoning_effort": "low"}),
    ("groq", "qwen/qwen3.8-27b", "off", {"reasoning_effort": "none"}),
    ("groq", "qwen/qwen3.8-27b", "high", {"reasoning_effort": "high"}),
    ("groq", "openai/gpt-oss-20b", "default", {}),
    ("gemini", "gemini-3.6-flash", "off", {"thinking_level": "MINIMAL"}),
    ("gemini", "gemini-3.6-flash", "default", {}),
    ("gemini", "gemini-2.5-flash", "default", {"thinking_budget": 0}),
    ("gemini", "gemini-2.5-pro", "off", {"thinking_budget": 128}),
    ("anthropic", "claude-sonnet-4-5", "high", {}),
])
def test_reasoning_levels_map_to_provider_parameters(provider, model, level, expected):
    assert reasoning_request(provider, model, level) == expected


def fake_client(config, responses):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item[0]), finish_reason=item[1])],
                               usage=None)

    client = LLMClient(config)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, requests


def groq(**values):
    return Settings(_env_file=None, LLM_PROVIDER="groq", GROQ_MODEL="qwen/qwen3.8-27b", GROQ_API_KEY="k", **values)


def test_call_level_overrides_profile_and_adds_output_headroom():
    client, requests = fake_client(groq(LLM_REASONING="high"), [("<think>nháp</think>LEGAL", "stop"), ("Trả lời", "stop")])
    assert client.complete("system", "user", max_tokens=10, reasoning="off") == "LEGAL"
    assert client.complete("system", "user", max_tokens=1500) == "Trả lời"
    assert [r["reasoning_effort"] for r in requests] == ["none", "high"]
    assert [r["max_tokens"] for r in requests] == [10 + 256, 1500 + 4096]


def test_rejected_reasoning_parameter_falls_back_once():
    error = RuntimeError("unsupported")
    error.status_code = 400
    client, requests = fake_client(groq(LLM_REASONING="low"), [error, ("OK", "stop"), ("OK", "stop")])
    assert client.complete("s", "u") == "OK" and client.complete("s", "u") == "OK"
    assert ["reasoning_effort" in r for r in requests] == [True, False, False]


def test_other_errors_are_not_retried():
    error = RuntimeError("quota")
    error.status_code = 429
    client, requests = fake_client(groq(LLM_REASONING="low"), [error])
    with pytest.raises(RuntimeError):
        client.complete("s", "u")
    assert len(requests) == 1


def test_reasoning_that_uses_the_output_limit_has_a_specific_message():
    client, _ = fake_client(groq(), [("<think>chưa xong", "length")])
    with pytest.raises(EmptyCompletion) as caught:
        client.complete("s", "u")
    code, message = configuration.failure_message(caught.value)
    assert code == "output_limit" and "suy luận" in message


def test_provider_server_errors_are_reported_as_temporary():
    error = RuntimeError("private")
    error.code = 503
    code, message = configuration.failure_message(error)
    assert code == "provider_error" and "private" not in message
