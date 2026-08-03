from __future__ import annotations

import re
from dataclasses import replace

from .parser import ChatMessage


PATTERNS = (
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号已隐藏]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[邮箱已隐藏]"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[身份证号已隐藏]"),
    (re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)"), "[长号码已隐藏]"),
)


def redact_messages(
    messages: list[ChatMessage], *, aliases: bool = True
) -> tuple[list[ChatMessage], dict[str, str], int]:
    speakers = list(dict.fromkeys(item.speaker for item in messages))
    alias_map = {name: f"参与者{chr(65 + index)}" for index, name in enumerate(speakers)}
    count = 0
    output: list[ChatMessage] = []

    for item in messages:
        body = item.text
        for pattern, replacement in PATTERNS:
            body, substitutions = pattern.subn(replacement, body)
            count += substitutions
        output.append(
            replace(
                item,
                speaker=alias_map[item.speaker] if aliases else item.speaker,
                text=body,
            )
        )
    return output, alias_map, count

