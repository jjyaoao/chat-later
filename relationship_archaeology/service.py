from __future__ import annotations

import json
from typing import Any

from .demo import build_demo_report
from .parser import ChatMessage, parse_chat, serialise_messages
from .privacy import redact_messages
from .prompts import (
    SYSTEM_PROMPT,
    build_analysis_prompt,
    build_audit_prompt,
    build_plan_prompt,
)
from .seed_client import SeedClient
from .stats import compute_stats


def analyse(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", ""))
    messages = parse_chat(text)
    if len(messages) < 5:
        raise ValueError("至少需要 5 条可识别消息；请使用页面展示的日期、姓名、正文格式。")
    if len(messages) > 100_000:
        raise ValueError("单次演示最多接收 100,000 条消息。")

    aliases_enabled = bool(payload.get("aliases", True))
    safe_messages, alias_map, redaction_count = redact_messages(
        messages, aliases=aliases_enabled
    )
    stats = compute_stats(safe_messages)
    client = SeedClient()
    deep = payload.get("mode", "deep") == "deep"

    if not client.configured:
        report = build_demo_report(safe_messages)
        plan: dict[str, Any] | None = None
        draft: dict[str, Any] | None = None
        engine = "local-demo"
        stages = ["本地解析", "敏感信息遮盖", "规则预览"]
    else:
        records = serialise_messages(safe_messages)
        sample_lines = records.splitlines()
        sample = "\n".join(sample_lines[:12] + sample_lines[-12:])
        print("[agent] 1/3 正在制定分析计划…", flush=True)
        plan = client.chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_plan_prompt(stats, sample)},
            ],
            max_tokens=30000,
        )
        print("[agent] 2/3 正在分析全量记录…", flush=True)
        draft = client.chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_analysis_prompt(stats, plan, records),
                },
            ],
            max_tokens=30000,
        )
        report = draft
        stages = ["本地解析", "敏感信息遮盖", "模型制定计划", "全量记录分析"]
        if deep:
            print("[agent] 3/3 正在审计报告证据…", flush=True)
            report = client.chat_json(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_audit_prompt(records, report),
                    },
                ],
                max_tokens=30000,
            )
            stages.append("证据审计")
        print("[agent] 模型阶段完成，正在映射证据…", flush=True)
        engine = client.model

    evidence = _collect_evidence(report, safe_messages)
    return {
        "engine": engine,
        "stages": stages,
        "stats": stats,
        "privacy": {
            "aliases_enabled": aliases_enabled,
            "alias_map": alias_map if aliases_enabled else {},
            "redaction_count": redaction_count,
        },
        "telemetry": client.calls,
        "analysis_trace": {
            "plan": plan,
            "draft": draft,
            "audited": bool(client.configured and deep),
            "audit_changed_report": bool(draft is not None and draft != report),
        },
        "report": report,
        "evidence": evidence,
    }


def preview(payload: dict[str, Any]) -> dict[str, Any]:
    messages = parse_chat(str(payload.get("text", "")))
    safe_messages, alias_map, redaction_count = redact_messages(
        messages, aliases=bool(payload.get("aliases", True))
    )
    return {
        "stats": compute_stats(safe_messages),
        "privacy": {"alias_map": alias_map, "redaction_count": redaction_count},
        "sample": [item.to_dict() for item in safe_messages[:8]],
    }


def _walk_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "evidence_ids" and isinstance(child, list):
                ids.update(str(item) for item in child)
            else:
                ids.update(_walk_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(_walk_ids(child))
    return ids


def _collect_evidence(report: dict, messages: list[ChatMessage]) -> dict[str, dict]:
    requested = _walk_ids(report)
    lookup = {item.id: item.to_dict() for item in messages}
    return {item_id: lookup[item_id] for item_id in sorted(requested) if item_id in lookup}


def markdown_export(result: dict[str, Any]) -> str:
    report = result["report"]
    lines = [
        f"# {report.get('title', '你们的后来')}",
        "",
        f"> {report.get('subtitle', '')}",
        "",
        report.get("overview", ""),
        "",
        "## 月度关系脉搏",
        "",
    ]
    for item in report.get("monthly", []):
        ids = ", ".join(item.get("evidence_ids", []))
        lines.append(
            f"- **{item.get('month', '')}**：温度 {item.get('warmth', '-')}/100，摩擦 {item.get('friction', '-')}/100。{item.get('summary', '')}（证据：{ids}）"
        )
    lines.extend(["", "## 转折点", ""])
    for item in report.get("turning_points", []):
        ids = ", ".join(item.get("evidence_ids", []))
        lines.append(
            f"- **{item.get('date', '')} · {item.get('title', '')}**：{item.get('observation', '')} 推断：{item.get('inference', '')}（证据：{ids}）"
        )
    lines.extend(["", "## 写在最后", "", report.get("closing_letter", "")])
    lines.extend(["", "---", report.get("confidence_note", "")])
    return "\n".join(lines)
