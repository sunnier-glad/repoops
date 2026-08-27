from __future__ import annotations

import json

import httpx


class LlmApiError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(transport=transport, timeout=30.0)

    def complete(self, prompt: str) -> dict[str, object]:
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "只输出 JSON，不要输出 Markdown。"},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        if response.is_error:
            raise LlmApiError(f"LLM 请求失败：HTTP {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LlmApiError("LLM 响应格式无效") from exc
        if not isinstance(parsed, dict):
            raise LlmApiError("LLM 输出不是 JSON 对象")
        return parsed
