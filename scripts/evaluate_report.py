from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relationship_archaeology.parser import parse_chat  # noqa: E402


def evidence_groups(value: Any) -> list[set[str]]:
    groups: list[set[str]] = []
    if isinstance(value, dict):
        ids = value.get("evidence_ids")
        if isinstance(ids, list):
            groups.append({str(item) for item in ids})
        for child in value.values():
            groups.extend(evidence_groups(child))
    elif isinstance(value, list):
        for child in value:
            groups.extend(evidence_groups(child))
    return groups


def _report_metrics(report: dict, truth: dict, valid_ids: set[str]) -> dict:
    groups = evidence_groups(report)
    cited = set().union(*groups) if groups else set()
    case_results = []
    for case in truth.get("cases", []):
        earlier = set(case["earlier"])
        later = set(case["later"])
        matching = [sorted(group) for group in groups if group & earlier and group & later]
        case_results.append(
            {
                "id": case["id"],
                "label": case["label"],
                "recalled": bool(matching),
                "matching_evidence_groups": matching,
            }
        )

    recalled = sum(item["recalled"] for item in case_results)
    total = len(case_results)
    invalid = sorted(cited - valid_ids)
    return {
        "cross_event_recall": {
            "recalled": recalled,
            "total": total,
            "rate": round(recalled / total, 4) if total else None,
            "cases": case_results,
        },
        "evidence_integrity": {
            "unique_cited_ids": len(cited),
            "cited_ids": sorted(cited),
            "invalid_ids": invalid,
            "valid_id_rate": round((len(cited) - len(invalid)) / len(cited), 4)
            if cited
            else None,
        },
    }


def _flatten_leaves(value: Any, path: str = "$") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            leaves.update(_flatten_leaves(value[key], f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.update(_flatten_leaves(child, f"{path}[{index}]"))
    else:
        leaves[path] = value
    return leaves


def _audit_impact(
    draft: dict | None, final: dict, truth: dict, valid_ids: set[str]
) -> dict | None:
    if not isinstance(draft, dict):
        return None
    draft_metrics = _report_metrics(draft, truth, valid_ids)
    final_metrics = _report_metrics(final, truth, valid_ids)
    draft_ids = set(draft_metrics["evidence_integrity"]["cited_ids"])
    final_ids = set(final_metrics["evidence_integrity"]["cited_ids"])
    before = _flatten_leaves(draft)
    after = _flatten_leaves(final)
    changed_paths = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )
    return {
        "report_changed": draft != final,
        "changed_leaf_count": len(changed_paths),
        "changed_path_sample": changed_paths[:30],
        "evidence_ids_removed": sorted(draft_ids - final_ids),
        "evidence_ids_added": sorted(final_ids - draft_ids),
        "invalid_ids_before": draft_metrics["evidence_integrity"]["invalid_ids"],
        "invalid_ids_after": final_metrics["evidence_integrity"]["invalid_ids"],
        "cross_event_recall_before": draft_metrics["cross_event_recall"]["recalled"],
        "cross_event_recall_after": final_metrics["cross_event_recall"]["recalled"],
    }


def evaluate(result: dict, truth: dict, valid_ids: set[str]) -> dict:
    report = result.get("report", {})
    report_metrics = _report_metrics(report, truth, valid_ids)
    telemetry = result.get("telemetry", [])
    prompt_tokens = sum(
        int(item.get("usage", {}).get("prompt_tokens", 0) or 0) for item in telemetry
    )
    completion_tokens = sum(
        int(item.get("usage", {}).get("completion_tokens", 0) or 0)
        for item in telemetry
    )
    return {
        "engine": result.get("engine"),
        "message_count": result.get("stats", {}).get("message_count"),
        "cross_event_recall": report_metrics["cross_event_recall"],
        "evidence_integrity": report_metrics["evidence_integrity"],
        "agent_run": {
            "model_calls": len(telemetry),
            "api_latency_seconds": round(
                sum(float(item.get("latency_seconds", 0) or 0) for item in telemetry), 3
            ),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "audited": result.get("analysis_trace", {}).get("audited", False),
            "audit_changed_report": result.get("analysis_trace", {}).get(
                "audit_changed_report", False
            ),
        },
        "audit_impact": _audit_impact(
            result.get("analysis_trace", {}).get("draft"),
            report,
            truth,
            valid_ids,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a live relationship report.")
    parser.add_argument("result", type=Path)
    parser.add_argument(
        "--truth", type=Path, default=ROOT / "sample_data" / "ground_truth.json"
    )
    parser.add_argument(
        "--chat", type=Path, default=ROOT / "sample_data" / "demo_chat.txt"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "output" / "evaluation.json"
    )
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    valid_ids = {item.id for item in parse_chat(args.chat.read_text(encoding="utf-8"))}
    evaluation = evaluate(result, truth, valid_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    recall = evaluation["cross_event_recall"]
    integrity = evaluation["evidence_integrity"]
    run = evaluation["agent_run"]
    print(f"Cross-event recall: {recall['recalled']}/{recall['total']}")
    print(f"Evidence ID integrity: {integrity['valid_id_rate']}")
    print(f"Model calls: {run['model_calls']}")
    print(f"Total tokens: {run['total_tokens']}")
    audit = evaluation.get("audit_impact")
    if audit:
        print(f"Audit changed JSON leaves: {audit['changed_leaf_count']}")
        print(
            "Invalid evidence IDs: "
            f"{len(audit['invalid_ids_before'])} -> {len(audit['invalid_ids_after'])}"
        )
        print(
            "Cross-event recall: "
            f"{audit['cross_event_recall_before']} -> {audit['cross_event_recall_after']}"
        )
    print(f"Saved: {args.output.resolve()}")


if __name__ == "__main__":
    main()
