from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from statistics import median

from .parser import ChatMessage, serialise_messages


COMMON_TERMS = (
    "吃饭", "早餐", "午饭", "晚饭", "夜宵", "咖啡", "奶茶", "做饭",
    "上班", "下班", "加班", "工作", "项目", "会议", "汇报", "面试",
    "学习", "考试", "作业", "论文", "代码", "实习", "求职", "同事",
    "周末", "旅行", "旅游", "散步", "骑车", "跑步", "爬山", "露营",
    "电影", "音乐", "演出", "展览", "游戏", "拍照", "相册", "照片",
    "生日", "礼物", "纪念日", "过年", "回家", "见面", "约会", "聚会",
    "开心", "难过", "生气", "抱歉", "谢谢", "晚安", "想你", "辛苦",
    "医院", "吃药", "休息", "睡觉", "天气", "下雨", "地铁", "航班",
    "计划", "约定", "下次", "改天", "以后", "明天", "今天", "昨天",
)
STOP_TERMS = {
    "一个", "一些", "一下", "已经", "还是", "就是", "这个", "那个", "什么",
    "怎么", "可以", "可能", "真的", "感觉", "觉得", "现在", "然后", "因为",
    "所以", "但是", "如果", "没有", "不是", "有点", "时候", "事情", "哈哈",
    "好的", "知道", "看到", "回来", "这样", "那样", "今天", "明天", "昨天",
}
EDGE_STOP_CHARS = set("的了是在和也就都还又把被给吗呢啊呀吧哦我你他她它们这那有没不很再才去来要会能说看想让")


def _parse_time(item: ChatMessage) -> datetime:
    return datetime.strptime(item.timestamp, "%Y-%m-%d %H:%M:%S")


def _longest_streak(days: list[str]) -> int:
    best = current = 0
    previous = None
    for raw in days:
        day = datetime.strptime(raw, "%Y-%m-%d").date()
        current = current + 1 if previous and (day - previous).days == 1 else 1
        best = max(best, current)
        previous = day
    return best


def _word_cloud(messages: list[ChatMessage], limit: int = 28) -> list[dict]:
    counts: Counter[str] = Counter()
    document_counts: Counter[str] = Counter()

    for item in messages:
        text = re.sub(r"https?://\S+|www\.\S+|\d{5,}", " ", item.text, flags=re.I)
        seen: set[str] = set()
        for term in COMMON_TERMS:
            hits = text.count(term)
            if hits:
                counts[term] += hits * 3
                seen.add(term)
        for latin in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,20}", text):
            normalised = latin.lower()
            if normalised not in {"http", "https", "www", "com"}:
                counts[normalised] += 2
                seen.add(normalised)
        for segment in re.findall(r"[\u4e00-\u9fff]{3,18}", text):
            for size in (2, 3):
                for index in range(len(segment) - size + 1):
                    term = segment[index : index + size]
                    if term in STOP_TERMS or term[0] in EDGE_STOP_CHARS or term[-1] in EDGE_STOP_CHARS:
                        continue
                    seen.add(term)
        document_counts.update(seen)

    for term, docs in document_counts.items():
        if term not in counts and docs >= 2:
            counts[term] = docs

    ranked = sorted(
        counts.items(),
        key=lambda pair: (pair[1] * (1.18 if len(pair[0]) >= 3 else 1), len(pair[0])),
        reverse=True,
    )
    selected: list[tuple[str, int]] = []
    for term, score in ranked:
        if score < 2 or any(term in chosen and chosen_score >= score for chosen, chosen_score in selected):
            continue
        selected.append((term, score))
        if len(selected) >= limit:
            break
    if not selected:
        return []
    maximum = max(score for _, score in selected)
    return [
        {"text": term, "count": score, "weight": max(1, min(5, round(score / maximum * 4) + 1))}
        for term, score in selected
    ]


def compute_stats(messages: list[ChatMessage]) -> dict:
    ordered = sorted(messages, key=lambda item: item.timestamp)
    per_speaker = Counter(item.speaker for item in ordered)
    per_month = Counter(item.month for item in ordered)
    daily_counts = Counter(item.timestamp[:10] for item in ordered)
    hourly_counts = Counter(item.hour for item in ordered)
    weekday_counts = Counter(_parse_time(item).weekday() for item in ordered)
    text_chars = sum(len(item.text) for item in ordered)
    serialised_chars = len(serialise_messages(ordered))
    late_night = sum(item.hour >= 23 or item.hour < 5 for item in ordered)

    reply_gaps: list[float] = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.speaker == current.speaker:
            continue
        gap = (_parse_time(current) - _parse_time(previous)).total_seconds() / 60
        if 0 <= gap <= 24 * 60:
            reply_gaps.append(gap)

    busiest_day, busiest_day_count = (None, 0)
    if daily_counts:
        busiest_day, busiest_day_count = daily_counts.most_common(1)[0]
    busiest_hour = hourly_counts.most_common(1)[0][0] if hourly_counts else None
    busiest_weekday = weekday_counts.most_common(1)[0][0] if weekday_counts else None
    active_days = sorted(daily_counts)

    return {
        "message_count": len(ordered),
        "character_count": text_chars,
        "serialised_character_count": serialised_chars,
        "estimated_tokens": round(serialised_chars / 1.7),
        "participants": list(per_speaker),
        "per_speaker": dict(per_speaker),
        "monthly_counts": dict(sorted(per_month.items())),
        "daily_counts": dict(sorted(daily_counts.items())),
        "hourly_counts": {str(hour): hourly_counts.get(hour, 0) for hour in range(24)},
        "late_night_count": late_night,
        "late_night_ratio": round(late_night / len(ordered) * 100, 1) if ordered else 0,
        "active_days": len(active_days),
        "longest_streak_days": _longest_streak(active_days),
        "busiest_day": busiest_day,
        "busiest_day_count": busiest_day_count,
        "busiest_hour": busiest_hour,
        "busiest_weekday": busiest_weekday,
        "median_reply_minutes": round(median(reply_gaps), 1) if reply_gaps else None,
        "word_cloud": _word_cloud(ordered),
        "start": ordered[0].timestamp if ordered else None,
        "end": ordered[-1].timestamp if ordered else None,
    }
