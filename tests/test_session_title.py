from types import SimpleNamespace

from src.backend.app.services.chat import generate_session_title, question_title


def runtime(reply):
    def complete(*args, **kwargs):
        if isinstance(reply, Exception):
            raise reply
        return reply
    return SimpleNamespace(chat=lambda: SimpleNamespace(llm=SimpleNamespace(complete=complete)))


def test_vietnamese_title_from_model_is_kept():
    assert generate_session_title(runtime('"Khái niệm kỷ luật lao động"'), "Kỷ luật lao động là gì?") == \
        "Khái niệm kỷ luật lao động"


def test_english_title_for_vietnamese_question_falls_back_to_question():
    assert generate_session_title(runtime("Concept of labor discipline"), "Kỷ luật lao động là gì?") == \
        "Kỷ luật lao động là gì?"


def test_failed_or_rambling_model_falls_back_to_question():
    assert generate_session_title(runtime(RuntimeError("down")), "Thời hạn báo trước") == "Thời hạn báo trước"
    long_reply = "Đây là " + "một tiêu đề rất dài " * 10
    assert generate_session_title(runtime(long_reply), "Thời hạn báo trước") == "Thời hạn báo trước"


def test_long_question_is_cut_at_a_word_boundary():
    title = question_title("Người lao động đơn phương chấm dứt hợp đồng lao động không xác định thời hạn phải báo trước bao lâu?")
    assert title.endswith("…") and len(title) <= 61 and not title[:-1].endswith(" ")
    assert "Người lao động đơn phương chấm dứt" in title
