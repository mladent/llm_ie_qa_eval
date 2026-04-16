from __future__ import annotations

from types import SimpleNamespace

from providers import gemini_provider, openai_provider


def test_run_openai_success(monkeypatch) -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"methods": []}'))],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )

    monkeypatch.setattr(openai_provider, "client", fake_client)

    result = openai_provider.run_openai("prompt", temperature=0.3, top_p=0.9, max_tokens=123)

    assert result["provider"] == "openai"
    assert result["parse_status"] == "success"
    assert result["parsed_output_json"] == {"methods": []}
    assert result["input_tokens"] == 11
    assert result["output_tokens"] == 7
    assert result["model_params_used"]["max_tokens"] == 123


def test_run_openai_parse_error(monkeypatch) -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="not-json"))],
        usage=None,
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    monkeypatch.setattr(openai_provider, "client", fake_client)

    result = openai_provider.run_openai("prompt")

    assert result["parse_status"] == "parse_error"
    assert result["parsed_output_json"] == {}
    assert result["error_message"] is not None


def test_run_gemini_success(monkeypatch) -> None:
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                text='{"tasks": ["ner"]}',
                usage_metadata=SimpleNamespace(
                    prompt_token_count=4,
                    candidates_token_count=2,
                ),
            )

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    class FakeTypes:
        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    monkeypatch.setattr(gemini_provider.genai, "Client", FakeClient)
    monkeypatch.setattr(gemini_provider.genai, "types", FakeTypes)

    result = gemini_provider.run_gemini("prompt", max_tokens=77)

    assert result["provider"] == "gemini"
    assert result["parse_status"] == "success"
    assert result["parsed_output_json"] == {"tasks": ["ner"]}
    assert result["input_tokens"] == 4
    assert result["output_tokens"] == 2
    assert result["model_params_used"]["max_tokens"] == 77


def test_run_gemini_parse_error(monkeypatch) -> None:
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text="not-json", usage_metadata=None)

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    class FakeTypes:
        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    monkeypatch.setattr(gemini_provider.genai, "Client", FakeClient)
    monkeypatch.setattr(gemini_provider.genai, "types", FakeTypes)

    result = gemini_provider.run_gemini("prompt")

    assert result["parse_status"] == "parse_error"
    assert result["error_message"] is not None
