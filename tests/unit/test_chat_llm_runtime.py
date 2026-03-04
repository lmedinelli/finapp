from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import app.services.market_data as market_data_module
from app.services.chat import ChatService


def _base_args() -> dict[str, Any]:
    return {
        "message": "Should I buy AAPL for the next 2 weeks?",
        "memory_messages": [{"role": "user", "content": "What about risk?"}],
        "symbol": "AAPL",
        "asset_type": "stock",
        "risk_profile": "balanced",
        "analysis": {"latest_close": 250.0, "rsi_14": 52.0},
        "recommendation": {
            "short_term": {"action": "hold", "confidence": 0.55},
            "long_term": {"action": "buy", "confidence": 0.66},
            "news_sentiment": {"score": 0.1, "label": "neutral"},
            "news": [],
        },
        "market_context": {"quote": {"price": 251.2, "change_percent": 0.4}},
        "workflow_steps": [],
    }


def _build_service(monkeypatch) -> ChatService:
    monkeypatch.setattr(market_data_module, "ensure_schema", lambda: None)
    return ChatService()


def test_generate_llm_answer_falls_back_to_candidate_model(monkeypatch) -> None:
    service = _build_service(monkeypatch)
    service.settings.openai_api_key = "test-key"
    service.settings.openai_model = "missing-model"
    service.settings.openai_admin_model_candidates = "missing-model,gpt-4.1-mini"

    response_calls: list[str] = []

    class FakeResponses:
        def create(self, **kwargs: Any) -> Any:
            model = str(kwargs.get("model", ""))
            response_calls.append(model)
            if model == "missing-model":
                raise RuntimeError("missing")
            return SimpleNamespace(output_text="Generated from fallback model.")

    class FakeChatCompletions:
        def create(self, **kwargs: Any) -> Any:
            raise AssertionError("chat.completions should not be used in this test")

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    args = _base_args()
    workflow_steps = args["workflow_steps"]
    answer = service._generate_llm_answer(**args)

    assert answer == "Generated from fallback model."
    assert response_calls[:2] == ["missing-model", "gpt-4.1-mini"]
    assert "llm:responses_success:gpt-4.1-mini" in workflow_steps
    assert "llm:model_fallback:missing-model->gpt-4.1-mini" in workflow_steps


def test_generate_llm_answer_uses_chat_completions_when_responses_fail(monkeypatch) -> None:
    service = _build_service(monkeypatch)
    service.settings.openai_api_key = "test-key"
    service.settings.openai_model = "gpt-4.1"
    service.settings.openai_admin_model_candidates = "gpt-4.1"

    class FakeResponses:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("responses unavailable")

    class FakeChatCompletions:
        def create(self, **kwargs: Any) -> Any:
            message = SimpleNamespace(content="Generated through chat completions.")
            choice = SimpleNamespace(message=message)
            return SimpleNamespace(choices=[choice])

    class FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()
            self.chat = SimpleNamespace(completions=FakeChatCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    args = _base_args()
    workflow_steps = args["workflow_steps"]
    answer = service._generate_llm_answer(**args)

    assert answer == "Generated through chat completions."
    assert any(step.startswith("llm:responses_error:gpt-4.1") for step in workflow_steps)
    assert "llm:chat_completions_success:gpt-4.1" in workflow_steps
