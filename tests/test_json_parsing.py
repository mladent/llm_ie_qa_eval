from __future__ import annotations

from providers.json_parsing import parse_json_object_text


def test_parse_json_object_text_handles_markdown_fence() -> None:
    text = """```json
{
  \"a\": [\"x\"],
  \"b\": []
}
```"""
    parsed, error = parse_json_object_text(text)
    assert error is None
    assert parsed == {"a": ["x"], "b": []}


def test_parse_json_object_text_handles_prefixed_text() -> None:
    text = "Answer:\n{\"k\": [\"v\"]}\nThanks"
    parsed, error = parse_json_object_text(text)
    assert error is None
    assert parsed == {"k": ["v"]}


def test_parse_json_object_text_rejects_non_object_json() -> None:
    parsed, error = parse_json_object_text("[1, 2, 3]")
    assert parsed is None
    assert error == "Parsed JSON is not an object"