from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relationship_archaeology.service import analyse  # noqa: E402
from relationship_archaeology.seed_client import SeedClientError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an authorised live Seed Evolving smoke test and save telemetry."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "sample_data" / "demo_chat.txt",
        help="Chat text you are authorised to send to the configured Ark API.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "live_smoke.json",
    )
    parser.add_argument("--quick", action="store_true", help="Skip evidence audit.")
    args = parser.parse_args()

    if not os.getenv("ARK_API_KEY", "").strip():
        raise SystemExit("ARK_API_KEY is not set. Configure it in the current shell first.")
    text = args.input.read_text(encoding="utf-8")
    try:
        result = analyse(
            {"text": text, "aliases": True, "mode": "quick" if args.quick else "deep"}
        )
    except SeedClientError as exc:
        raise SystemExit(f"Live test stopped: {exc}") from None
    if result["engine"] == "local-demo":
        raise SystemExit("Live test unexpectedly used the local demo engine.")
    expected_calls = 2 if args.quick else 3
    if len(result["telemetry"]) != expected_calls:
        raise SystemExit(
            f"Expected {expected_calls} model calls, got {len(result['telemetry'])}."
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_latency = sum(item.get("latency_seconds", 0) for item in result["telemetry"])
    print(f"Live model: {result['engine']}")
    print(f"Messages: {result['stats']['message_count']}")
    print(f"Model calls: {len(result['telemetry'])}")
    print(f"Accumulated API latency: {total_latency:.3f}s")
    print(f"Saved: {args.output.resolve()}")
    print("Next: python scripts/evaluate_report.py output/live_smoke.json")


if __name__ == "__main__":
    main()
