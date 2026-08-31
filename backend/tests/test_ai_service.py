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


def test_ai_service_validates_release_notes_polish_contract():
    service = AiService(
        FakeLlm(
            {
                "summary": "压缩重复表达",
                "suggested_content": "# v1.0.0\n\n- Improve docs",
                "changes": ["压缩重复表达"],
            }
        ),
        "demo-model",
    )

    result = service.polish_release_notes(
        "v1.0.0", "# v1.0.0\n\n- Improve docs", "#3 Improve docs"
    )

    assert result.analysis_type == "release_notes_polish"
    assert result.content["suggested_content"].startswith("# v1.0.0")
    assert result.content["changes"] == ["压缩重复表达"]


def test_ai_service_rejects_release_notes_without_change_list():
    service = AiService(
        FakeLlm(
            {
                "summary": "有建议",
                "suggested_content": "# v1.0.0",
            }
        ),
        "demo-model",
    )

    with pytest.raises(AiOutputError, match="changes"):
        service.polish_release_notes("v1.0.0", "# v1.0.0", "#3 Improve docs")
