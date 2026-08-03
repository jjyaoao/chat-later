from __future__ import annotations

from collections import Counter

from .parser import ChatMessage, serialise_messages


def compute_stats(messages: list[ChatMessage]) -> dict:
    per_speaker = Counter(item.speaker for item in messages)
    per_month = Counter(item.month for item in messages)
    text_chars = sum(len(item.text) for item in messages)
    serialised_chars = len(serialise_messages(messages))
    late_night = sum(item.hour >= 23 or item.hour < 5 for item in messages)
    return {
        "message_count": len(messages),
        "character_count": text_chars,
        "serialised_character_count": serialised_chars,
        "estimated_tokens": round(serialised_chars / 1.7),
        "participants": list(per_speaker),
        "per_speaker": dict(per_speaker),
        "monthly_counts": dict(sorted(per_month.items())),
        "late_night_count": late_night,
        "start": messages[0].timestamp if messages else None,
        "end": messages[-1].timestamp if messages else None,
    }
