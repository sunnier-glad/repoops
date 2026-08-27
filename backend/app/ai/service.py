from __future__ import annotations

from dataclasses import dataclass


class AiOutputError(ValueError):
    """The model output does not satisfy the product contract."""


@dataclass(frozen=True)
class AiResult:
    analysis_type: str
    model: str
    content: dict[str, object]


class AiService:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def summarize_pull_request(self, title: str, body: str | None) -> AiResult:
        return self._complete(
            "pull_request_summary",
            f"PR 标题：{title}\nPR 描述：{body or '无'}",
            "summary",
        )

    def explain_workflow_failure(self, workflow_name: str, logs: str) -> AiResult:
        return self._complete(
            "workflow_failure_explanation",
            f"Workflow：{workflow_name}\n失败日志：{logs}",
            "explanation",
        )

    def generate_release_notes(self, tag_name: str, changes: str) -> AiResult:
        return self._complete(
            "release_notes",
            f"版本：{tag_name}\n变更：{changes}",
            "notes",
        )

    def _complete(self, analysis_type: str, prompt: str, required_key: str) -> AiResult:
        content = self.client.complete(prompt)
        if not isinstance(content, dict):
            raise AiOutputError("AI 输出不是 JSON 对象")
        value = content.get(required_key)
        if not isinstance(value, str) or not value.strip():
            raise AiOutputError(f"AI 输出缺少有效字段：{required_key}")
        return AiResult(analysis_type, self.model, content)
