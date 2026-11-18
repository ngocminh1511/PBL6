"""Unit tests for query intent classification and direct conversation flow."""
from labor_rag.generation.intent import is_legal_query, generate_direct_answer


def test_greeting_and_social_chitchat_are_classified_as_non_legal():
    assert not is_legal_query("xin chào")
    assert not is_legal_query("Chào bạn!")
    assert not is_legal_query("hello")
    assert not is_legal_query("hi")
    assert not is_legal_query("cảm ơn bạn nhé")
    assert not is_legal_query("thanks")
    assert not is_legal_query("tạm biệt")
    assert not is_legal_query("bạn là ai")


def test_llm_classification_routes_general_and_legal(monkeypatch):
    import labor_rag.generation.intent as intent_mod

    # Mock LLM answering GENERAL for off-topic query
    monkeypatch.setattr(intent_mod, "complete", lambda *args, **kwargs: "GENERAL")
    assert not is_legal_query("thời tiết hôm nay thế nào")

    # Mock LLM answering LEGAL for labor law question
    monkeypatch.setattr(intent_mod, "complete", lambda *args, **kwargs: "LEGAL")
    assert is_legal_query("thời hạn báo trước khi đơn phương chấm dứt hợp đồng")


def test_direct_answer_returns_friendly_response(monkeypatch):
    import labor_rag.generation.intent as intent_mod
    monkeypatch.setattr(intent_mod, "complete", lambda *args, **kwargs: "Xin chào bạn! Tôi là trợ lý pháp luật.")
    ans = generate_direct_answer("xin chào")
    assert "trợ lý" in ans


def test_fallback_on_exception_defaults_to_legal(monkeypatch):
    import labor_rag.generation.intent as intent_mod
    monkeypatch.setattr(intent_mod, "complete", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("API error")))
    assert is_legal_query("Quy định thời hạn thử việc")


def test_chat_pipeline_skips_retrieval_for_greetings(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from labor_rag.services.chat import ChatPipeline
    from labor_rag.settings import Settings
    import labor_rag.generation.intent as intent_mod

    monkeypatch.setattr(intent_mod, "complete", lambda *args, **kwargs: "Xin chào bạn!")
    retriever_called = []
    retriever = SimpleNamespace(
        retrieve=lambda *args, **kwargs: retriever_called.append(True) or [],
        vector_search=lambda *args, **kwargs: retriever_called.append(True) or [],
    )
    catalog = SimpleNamespace(last_attachments=[], last_warnings=[])
    settings = Settings(_env_file=None, DATABASE_URL="sqlite://", REDIS_ENABLED=False)

    pipeline = ChatPipeline(retriever, catalog, settings)
    result = pipeline.ask("xin chào")

    assert not retriever_called, "Retrieval must not be called for greetings"
    assert result["evidence"] == []
    assert result["pipeline_trace"] is None
    assert "Xin chào" in result["answer"]

