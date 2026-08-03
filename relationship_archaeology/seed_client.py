from __future__ import annotations

import json
import hashlib
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class SeedClientError(RuntimeError):
    pass


class SeedClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("ARK_API_KEY", "").strip()
        self.base_url = os.getenv(
            "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
        ).rstrip("/")
        self.model = os.getenv("ARK_MODEL", "doubao-seed-evolving")
        self.api_style = os.getenv("ARK_API_STYLE", "responses").strip().lower()
        configured_timeout = int(os.getenv("ARK_TIMEOUT_SECONDS", "600"))
        self.timeout_seconds = min(1800, max(30, configured_timeout))
        self.max_retries = min(5, max(0, int(os.getenv("ARK_MAX_RETRIES", "3"))))
        self.force_json_tool = os.getenv("ARK_FORCE_JSON_TOOL", "0") == "1"
        cache_dir = os.getenv("ARK_RESPONSE_CACHE_DIR", "").strip()
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.calls: list[dict[str, Any]] = []

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 30000,
    ) -> dict[str, Any]:
        if not self.configured:
            raise SeedClientError("ARK_API_KEY is not configured")
        if self.api_style != "responses":
            raise SeedClientError(
                "ARK_API_STYLE currently supports only 'responses' for Seed Evolving"
            )
        payload = _build_responses_payload(
            messages,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            force_json_tool=self.force_json_tool,
        )
        encoded_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=encoded_payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.monotonic()
        retry_count = 0
        cache_path = self._cache_path(encoded_payload)
        cached = bool(cache_path and cache_path.exists())
        if cached:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            while True:
                try:
                    with urllib.request.urlopen(
                        request, timeout=self.timeout_seconds
                    ) as response:
                        raw = json.loads(response.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    if exc.code == 429 and retry_count < self.max_retries:
                        retry_count += 1
                        retry_after = exc.headers.get("Retry-After")
                        try:
                            delay = float(retry_after) if retry_after else 15 * retry_count
                        except ValueError:
                            delay = 15 * retry_count
                        time.sleep(min(45, max(1, delay)))
                        continue
                    raise SeedClientError(
                        _friendly_http_error(exc.code, detail, self.base_url, self.model)
                    ) from exc
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                    raise SeedClientError(f"Ark API request failed: {exc}") from exc
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
                )

        content = _extract_responses_text(raw)
        raw_usage = raw.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get(
                "input_tokens", raw_usage.get("prompt_tokens", 0)
            ),
            "completion_tokens": raw_usage.get(
                "output_tokens", raw_usage.get("completion_tokens", 0)
            ),
            "total_tokens": raw_usage.get("total_tokens", 0),
        }
        self.calls.append(
            {
                "model": raw.get("model", self.model),
                "api": "responses",
                "latency_seconds": round(time.monotonic() - started, 3),
                "finish_reason": raw.get("status"),
                "retries": retry_count,
                "cached": cached,
                "usage": usage,
            }
        )
        return _extract_json(content)

    def _cache_path(self, encoded_payload: bytes) -> Path | None:
        if not self.cache_dir:
            return None
        digest = hashlib.sha256(encoded_payload).hexdigest()
        return self.cache_dir / f"{digest}.json"


def _build_responses_payload(
    messages: list[dict[str, str]],
    *,
    model: str,
    temperature: float,
    max_tokens: int,
    force_json_tool: bool = True,
) -> dict[str, Any]:
    """Translate our compact message format to Ark's Responses API schema."""
    instructions: list[str] = []
    input_items: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = str(message.get("content", ""))
        if role in {"system", "developer"}:
            instructions.append(content)
            continue
        input_items.append(
            {
                "role": role if role in {"user", "assistant"} else "user",
                "content": [{"type": "input_text", "text": content}],
            }
        )
    payload: dict[str, Any] = {
        "model": model,
        "input": input_items,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if instructions:
        payload["instructions"] = "\n\n".join(instructions)
    if force_json_tool:
        payload["tools"] = [
            {
                "type": "function",
                "name": "return_json",
                "description": "Return the final answer as one JSON object.",
                "parameters": {"type": "object", "additionalProperties": True},
            }
        ]
        payload["tool_choice"] = {"type": "function", "name": "return_json"}
    return payload


def _extract_responses_text(raw: dict[str, Any]) -> str:
    """Collect output_text blocks from a raw Responses API response."""
    chunks: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call" and item.get("name") == "return_json":
            arguments = item.get("arguments", "")
            chunks.append(
                json.dumps(arguments, ensure_ascii=False)
                if isinstance(arguments, dict)
                else str(arguments)
            )
        for block in item.get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") in {"output_text", "text"}:
                chunks.append(str(block.get("text", "")))
    if not chunks:
        incomplete_reason = (raw.get("incomplete_details") or {}).get("reason")
        if raw.get("status") == "incomplete" and incomplete_reason:
            raise SeedClientError(
                "Ark Responses API did not produce final output "
                f"(incomplete: {incomplete_reason}). Increase max_output_tokens."
            )
        raise SeedClientError(f"Unexpected Ark Responses payload: {str(raw)[:500]}")
    return "".join(chunks)


def _extract_json(content: str | list) -> dict[str, Any]:
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    cleaned = str(content).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise SeedClientError("The model response did not contain a JSON object")
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SeedClientError(f"Could not parse model JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SeedClientError("The model JSON response was not an object")
    return parsed


def _friendly_http_error(status: int, detail: str, base_url: str, model: str) -> str:
    """Turn common Ark gateway errors into actionable messages without account data."""
    if "SetLimitExceeded" in detail:
        return (
            "Ark 安全体验模式的推理上限已触发，模型服务已暂停。"
            "请在模型开通管理页调整推理上限或关闭安全体验模式后重试。"
        )
    if "ModelNotOpen" in detail:
        return (
            f"模型 {model} 尚未在这枚标准 Ark API Key 所属账号中开通。"
            "请进入模型详情页，点击“API 接入/开通服务”，完成后重试。"
        )
    if status == 401 and "/api/plan/" in f"{base_url}/":
        return (
            "当前 API Key 不能用于 Agent Plan 网关。标准 Ark Key 与 Agent Plan Key "
            "不能混用；请改用套餐专属 Key，或将 ARK_BASE_URL 切回 /api/v3。"
        )
    if status == 401:
        return "Ark API 鉴权失败。请检查 API Key 是否完整、有效并属于当前网关。"
    return f"Ark API returned HTTP {status}: {detail[:500]}"
