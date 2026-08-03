from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable


INLINE_PATTERNS = (
    re.compile(
        r"^\[(?P<date>\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[^:：]{1,40})[:：]\s*(?P<text>.*)$"
    ),
    re.compile(
        r"^(?P<date>\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<speaker>[^:：]{1,40})[:：]\s*(?P<text>.*)$"
    ),
)
HEADER_PATTERN = re.compile(
    r"^(?P<date>\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\s+(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s+(?P<speaker>.{1,40})$"
)
SEPARATOR_PATTERN = re.compile(r"^[-=_*]{5,}$")
CSV_TIME_FIELDS = ("timestamp", "datetime", "date", "日期时间", "日期", "时间")
CSV_CLOCK_FIELDS = ("clock", "time", "时刻")
CSV_SPEAKER_FIELDS = ("speaker", "name", "sender", "from", "昵称", "发送者", "姓名")
CSV_TEXT_FIELDS = ("text", "content", "message", "body", "消息", "内容", "正文")


@dataclass(frozen=True)
class ChatMessage:
    id: str
    timestamp: str
    speaker: str
    text: str

    @property
    def month(self) -> str:
        return self.timestamp[:7]

    @property
    def hour(self) -> int:
        return int(self.timestamp[11:13])

    def to_dict(self) -> dict:
        return asdict(self)


def _normalise_datetime(date_text: str, time_text: str) -> str:
    raw = f"{date_text.replace('/', '-').replace('.', '-')} {time_text}"
    formats = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp: {raw}")


def _normalise_full_timestamp(value: str) -> str:
    cleaned = value.strip().replace("/", "-").replace(".", "-").replace("T", " ")
    try:
        return datetime.fromisoformat(cleaned).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %p %I:%M:%S",
        "%Y-%m-%d %p %I:%M",
    ):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp: {value}")


def _field_lookup(fieldnames: list[str] | None) -> dict[str, str]:
    return {
        name.strip().lstrip("\ufeff").casefold(): name
        for name in (fieldnames or [])
        if name
    }


def _pick_field(lookup: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return None


def _parse_csv(text: str) -> list[tuple[str, str, str]] | None:
    first_line = text.lstrip("\ufeff").splitlines()[0] if text.strip() else ""
    if not any(delimiter in first_line for delimiter in (",", ";", "\t")):
        return None
    try:
        dialect = csv.Sniffer().sniff(first_line, delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), dialect=dialect)
    except csv.Error:
        return None
    lookup = _field_lookup(reader.fieldnames)
    date_field = _pick_field(lookup, CSV_TIME_FIELDS)
    speaker_field = _pick_field(lookup, CSV_SPEAKER_FIELDS)
    text_field = _pick_field(lookup, CSV_TEXT_FIELDS)
    if not (date_field and speaker_field and text_field):
        return None
    clock_field = _pick_field(lookup, CSV_CLOCK_FIELDS)
    output: list[tuple[str, str, str]] = []
    for row in reader:
        raw_date = str(row.get(date_field) or "").strip()
        speaker = str(row.get(speaker_field) or "").strip()
        body = str(row.get(text_field) or "").strip()
        if not (raw_date and speaker and body):
            continue
        if ":" not in raw_date and clock_field and clock_field != date_field:
            raw_date = f"{raw_date} {str(row.get(clock_field) or '').strip()}"
        try:
            timestamp = _normalise_full_timestamp(raw_date)
        except ValueError:
            continue
        output.append((timestamp, speaker, body))
    return output if output else None


def parse_chat(text: str) -> list[ChatMessage]:
    """Parse common plain-text chat exports without depending on WeChat internals."""
    csv_messages = _parse_csv(text)
    if csv_messages is not None:
        return [
            ChatMessage(id=f"E{index:05d}", timestamp=ts, speaker=speaker, text=body)
            for index, (ts, speaker, body) in enumerate(csv_messages, start=1)
        ]

    messages: list[tuple[str, str, str]] = []
    pending: tuple[str, str] | None = None

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip("\ufeff")
        matched = None
        for pattern in INLINE_PATTERNS:
            matched = pattern.match(line)
            if matched:
                break
        if matched:
            pending = None
            timestamp = _normalise_datetime(matched["date"], matched["time"])
            messages.append((timestamp, matched["speaker"].strip(), matched["text"].strip()))
            continue

        header = HEADER_PATTERN.match(line)
        if header:
            pending = (
                _normalise_datetime(header["date"], header["time"]),
                header["speaker"].strip(),
            )
            continue

        if SEPARATOR_PATTERN.match(line.strip()):
            pending = None
            continue
        if pending and line.strip():
            messages.append((pending[0], pending[1], line.strip()))
            pending = None
        elif messages and line.strip():
            timestamp, speaker, previous = messages[-1]
            messages[-1] = (timestamp, speaker, previous + "\n" + line.strip())

    return [
        ChatMessage(id=f"E{index:05d}", timestamp=ts, speaker=speaker, text=body)
        for index, (ts, speaker, body) in enumerate(messages, start=1)
    ]


def serialise_messages(messages: Iterable[ChatMessage]) -> str:
    return "\n".join(
        f"{item.id}\t{item.timestamp}\t{item.speaker}\t{item.text.replace(chr(9), ' ')}"
        for item in messages
    )
