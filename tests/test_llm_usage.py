"""Reported token counts, request isolation and persisted chat contracts; no cloud calls."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from labor_rag.generation.llm_client import LLMClient
from labor_rag.generation.usage import collect_usage, response_usage, usage_stage
from labor_rag.services.chat import ChatPipeline
from labor_rag.settings import Settings
from src.backend.app.main import create_app
from src.backend.app.models.database import ChatMessage


@pytest.mark.parametrize("provider,response,expected", [
    ("groq", {"usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14,
         "prompt_tokens_details": {"cached_tokens": 3}, "completion_tokens_details": {"reasoning_tokens": 2}}},
     {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14, "cached_input_tokens": 3, "reasoning_tokens": 2}),
    ("gemini", {"usage_metadata": {"prompt_token_count": 10, "candidates_token_count": 4,
         "thoughts_token_count": 3, "total_token_count": 17, "cached_content_token_count": 2}},
     {"input_tokens": 10, "output_tokens": 7, "total_tokens": 17, "cached_input_tokens": 2, "reasoning_tokens": 3}),
    ("anthropic", {"usage": {"input_tokens": 10, "cache_read_input_tokens": 5,
         "cache_creation_input_tokens": 2, "output_tokens": 3}},
     {"input_tokens": 17, "output_tokens": 3, "total_tokens": 20, "cached_input_tokens": 5, "reasoning_tokens": None}),
    ("local", {"usage": {"prompt_tokens": 0, "completion_tokens": 0}},
     {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_input_tokens": None, "reasoning_tokens": None}),
    ("local", {}, {"input_tokens": None, "output_tokens": None, "total_tokens": None,
                   "cached_input_tokens": None, "reasoning_tokens": None}),
])
def test_normalizes_reported_counts_without_estimates_or_double_counting(provider, response, expected):
    assert response_usage(response, provider) == expected


def settings(tmp_path):
    return Settings(_env_file=None, DATABASE_URL="sqlite://", REDIS_ENABLED=False, REDIS_URL="",
                    LLM_PROVIDER="groq", GROQ_MODEL="test-model", DEMO_MODE=True,
                    UPLOAD_DIR=tmp_path / "uploads", INTERIM_DIR=tmp_path / "interim")


def fake_llm(config, *, legal=False, failure=None, report_usage=True):
    requests = []

    def create(**kwargs):
        requests.append(kwargs)
        system = kwargs["messages"][0]["content"]
        if "đặt tên" in system:
            content, incoming, outgoing = "Chào hỏi", 101, 7
        elif "phân loại" in system:
            content, incoming, outgoing = "LEGAL" if legal else "GENERAL", 41, 1
        else:
            if failure:
                raise failure
            content, incoming, outgoing = "Xin chào bạn.", 51, 9
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=incoming, completion_tokens=outgoing,
                                  total_tokens=incoming + outgoing) if report_usage else None)

    client = LLMClient(config)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return client, requests


def test_greeting_counts_title_and_reply_and_survives_history_reload(tmp_path, monkeypatch):
    config = settings(tmp_path)
    app = create_app(settings=config)
    llm, requests = fake_llm(config)
    monkeypatch.setattr(app.state.runtime, "chat",
        lambda: ChatPipeline(SimpleNamespace(), app.state.runtime.catalog, config, llm=llm))
    with TestClient(app) as client:
        response = client.post("/api/chat/ask", json={"question": "xin chào"})
        assert response.status_code == 200
        result = response.json()
        usage = result["assistant_message"]["token_usage"]
        assert usage["status"] == "complete"
        assert (usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]) == (152, 16, 168)
        assert [call["stage"] for call in usage["calls"]] == ["session_title", "generation"]
        assert "intent" in usage["executed_stages"] and "retrieval" not in usage["executed_stages"]
        stored = client.get("/api/chat/sessions/" + result["session_id"]).json()
        assert stored["messages"][1]["token_usage"] == usage
        followup = client.post("/api/chat/ask", json={"session_id": result["session_id"], "question": "xin chào"}).json()
        next_usage = followup["assistant_message"]["token_usage"]
        assert next_usage["total_tokens"] == 60 and len(next_usage["calls"]) == 1
        assert len(requests) == 3
        assert "user: xin chào" in requests[-1]["messages"][1]["content"]


def test_unknown_provider_usage_stays_unavailable_instead_of_zero(tmp_path, monkeypatch):
    config = settings(tmp_path)
    llm, _ = fake_llm(config, report_usage=False)
    result = ChatPipeline(SimpleNamespace(), SimpleNamespace(), config, llm=llm).ask("xin chào")
    assert result["token_usage"]["status"] == "unavailable"
    assert result["token_usage"]["total_tokens"] is None
    assert result["token_usage"]["calls"][0]["input_tokens"] is None


def test_legal_followup_records_rewrite_rerank_and_generation(tmp_path):
    from labor_rag.retrieval.hybrid_retrieve import Evidence
    from labor_rag.appendices.runtime import AppendixCatalog
    config = settings(tmp_path)
    llm, _ = fake_llm(config, legal=True)
    items = [Evidence(f"law:d{i}", None, f"Điều {i}", "Chứng cứ", "vector", document_id="law")
             for i in range(6)]
    retriever = SimpleNamespace(retrieve=lambda *a, **kw: items, graph_warning=None)
    result = ChatPipeline(retriever, AppendixCatalog(tmp_path), config, llm=llm).ask(
        "Còn thời hạn thì sao?", history=[{"role": "user", "content": "Câu hỏi trước"}])
    usage = result["token_usage"]
    assert [call["stage"] for call in usage["calls"]] == ["intent", "query_rewrite", "rerank", "generation"]
    assert usage["status"] == "complete" and usage["total_tokens"] == 222
    assert {"retrieval", "appendices", "verification"} <= set(usage["executed_stages"])


def test_failed_direct_reply_is_visible_even_when_fallback_returns_text(tmp_path, monkeypatch):
    config = settings(tmp_path)
    app = create_app(settings=config)
    failure = RuntimeError("private-prompt-and-key; Requested 6864")
    failure.status_code = 429
    llm, _ = fake_llm(config, failure=failure)
    monkeypatch.setattr(app.state.runtime, "chat",
        lambda: ChatPipeline(SimpleNamespace(), app.state.runtime.catalog, config, llm=llm))
    with TestClient(app) as client:
        response = client.post("/api/chat/ask", json={"question": "xin chào"})
        assert response.status_code == 200  # the pre-existing friendly fallback still works
        usage = response.json()["assistant_message"]["token_usage"]
        assert usage["status"] == "partial" and usage["total_tokens"] == 108
        assert usage["calls"][-1]["status"] == "failed"
        assert usage["calls"][-1]["requested_tokens"] == 6864
        assert usage["calls"][-1]["input_tokens"] is None
        assert "private-prompt-and-key" not in response.text


def test_legal_failure_returns_usage_without_saving_fake_messages(tmp_path, monkeypatch):
    config = settings(tmp_path)
    app = create_app(settings=config)
    failure = RuntimeError("private-provider-message; Requested 8000")
    failure.status_code = 413
    llm, _ = fake_llm(config, legal=True, failure=failure)
    retriever = SimpleNamespace(retrieve=lambda *a, **kw: [], graph_warning=None)
    monkeypatch.setattr(app.state.runtime, "chat",
        lambda: ChatPipeline(retriever, app.state.runtime.catalog, config, llm=llm))
    with TestClient(app) as client:
        response = client.post("/api/chat/ask", json={"question": "Người dưới 15 tuổi không được làm gì?"})
        assert response.status_code == 503
        usage = response.json()["token_usage"]
        assert usage["status"] == "partial" and usage["total_tokens"] == 150
        assert usage["calls"][-1]["requested_tokens"] == 8000
        assert "private-provider-message" not in response.text
        with app.state.database.session() as db:
            assert db.query(ChatMessage).count() == 0


def test_collectors_do_not_leak_between_concurrent_requests(tmp_path):
    barrier = Barrier(2)

    def request(stage):
        llm, _ = fake_llm(settings(tmp_path))
        with collect_usage() as usage, usage_stage(stage):
            barrier.wait(timeout=5)
            llm.complete("system", "question")
            return usage.snapshot()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, ["generation", "intent"]))
    assert [len(result["calls"]) for result in results] == [1, 1]
    assert [result["calls"][0]["stage"] for result in results] == ["generation", "intent"]


def test_request_scope_is_reset_after_exception(tmp_path):
    with pytest.raises(RuntimeError), collect_usage():
        raise RuntimeError("stop")
    with collect_usage() as usage:
        assert usage.snapshot()["calls"] == []
