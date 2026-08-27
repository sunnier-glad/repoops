import pytest

from app.ai.service import AiOutputError, AiService


class FakeLlm:
    def __init__(self, response):
        self.response = response

    def complete(self, prompt: str):
        assert "Improve docs" in prompt
        return self.response


def test_ai_service_validates_structured_pr_summary():
    service = AiService(FakeLlm({"summary": "整理了文档变更", "risks": ["无"]}), "demo-model")

    result = service.summarize_pull_request("Improve docs", "Details")

    assert result.analysis_type == "pull_request_summary"
    assert result.content["summary"] == "整理了文档变更"
    assert result.model == "demo-model"


def test_ai_service_rejects_empty_or_invalid_output():
    service = AiService(FakeLlm({"summary": ""}), "demo-model")

    with pytest.raises(AiOutputError):
        service.summarize_pull_request("Improve docs", "Details")
