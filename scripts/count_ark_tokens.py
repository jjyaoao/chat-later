from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relationship_archaeology.parser import parse_chat, serialise_messages  # noqa: E402
from relationship_archaeology.privacy import redact_messages  # noqa: E402
from relationship_archaeology.prompts import build_analysis_prompt  # noqa: E402
from relationship_archaeology.stats import compute_stats  # noqa: E402


def count_chunk(endpoint: str, api_key: str, model: str, text: str) -> int:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps({"model": model, "text": [text]}, ensure_ascii=False).encode(
            "utf-8"
        ),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tokenization HTTP {exc.code}: {detail[:500]}") from exc
    item = raw.get("data", [{}])[0]
    count = item.get("total_tokens")
    if count is None:
        count = len(item.get("tokens", item.get("token_ids", [])))
    if not count:
        raise RuntimeError(f"Unexpected tokenization response: {str(raw)[:500]}")
    return int(count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Count an Ark analysis prompt exactly.")
    parser.add_argument("chat", type=Path)
    parser.add_argument("--chunk-chars", type=int, default=100_000)
    args = parser.parse_args()

    api_key = os.getenv("ARK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ARK_API_KEY is not set.")
    model = os.getenv("ARK_MODEL", "doubao-seed-evolving")
    base_url = os.getenv(
        "ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
    ).rstrip("/")

    messages = parse_chat(args.chat.read_text(encoding="utf-8"))
    safe_messages, _, _ = redact_messages(messages, aliases=True)
    records = serialise_messages(safe_messages)
    prompt = build_analysis_prompt(compute_stats(safe_messages), {}, records)
    chunks = [
        prompt[index : index + args.chunk_chars]
        for index in range(0, len(prompt), args.chunk_chars)
    ]
    total = 0
    for index, chunk in enumerate(chunks, start=1):
        total += count_chunk(f"{base_url}/tokenization", api_key, model, chunk)
        print(f"Chunk {index}/{len(chunks)}: cumulative {total} tokens", flush=True)
        if index < len(chunks):
            time.sleep(1)
    print(f"Prompt characters: {len(prompt)}")
    print(f"Exact chunked tokens: {total}")


if __name__ == "__main__":
    main()
