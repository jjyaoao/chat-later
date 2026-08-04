from __future__ import annotations

from collections import Counter, defaultdict

from .parser import ChatMessage


POSITIVE = ("哈哈", "谢谢", "好呀", "可以", "辛苦", "晚安", "加油", "想你", "开心", "好耶")
FRICTION = ("算了", "生气", "烦", "别", "不想", "为什么", "失望", "抱歉", "对不起")
TOPICS = {
    "日常碎片": ("吃", "早", "晚安", "下班", "到家", "天气"),
    "一起出发": ("去", "周末", "旅行", "票", "展", "电影"),
    "工作与成长": ("工作", "项目", "面试", "学习", "考试", "汇报"),
    "情绪支持": ("累", "难过", "加油", "抱抱", "别怕", "辛苦"),
}


def build_demo_report(messages: list[ChatMessage]) -> dict:
    per_month: dict[str, list[ChatMessage]] = defaultdict(list)
    for item in messages:
        per_month[item.month].append(item)

    monthly = []
    for month, items in sorted(per_month.items()):
        joined = " ".join(item.text for item in items)
        positive = sum(joined.count(word) for word in POSITIVE)
        friction = sum(joined.count(word) for word in FRICTION)
        monthly.append(
            {
                "month": month,
                "warmth": min(92, 48 + positive * 5),
                "friction": min(82, 8 + friction * 7),
                "summary": f"这个月留下了 {len(items)} 条消息，更多细节需要 Seed Evolving 完整分析。",
                "evidence_ids": [item.id for item in items[:2]],
            }
        )

    topic_scores = Counter()
    topic_evidence: dict[str, list[str]] = defaultdict(list)
    for item in messages:
        for topic, keywords in TOPICS.items():
            if any(keyword in item.text for keyword in keywords):
                topic_scores[topic] += 1
                if len(topic_evidence[topic]) < 3:
                    topic_evidence[topic].append(item.id)
    total = sum(topic_scores.values()) or 1
    topics = [
        {
            "name": topic,
            "share": round(score / total * 100),
            "change": "本地演示仅做关键词预览",
            "evidence_ids": topic_evidence[topic],
        }
        for topic, score in topic_scores.most_common(4)
    ]
    evidence = [item.id for item in messages]
    return {
        "title": "你们这一年的后来",
        "subtitle": "真正重要的变化，常常藏在重复出现的小事里",
        "overview": "这是未连接模型时的本地预览。它用规则展示报告形态；连接 Doubao-Seed-Evolving 后，模型会读取完整记录，重建跨月事件与互动变化，并由第二轮审计核对证据。",
        "confidence_note": "当前为本地演示引擎，不能替代模型深度分析。评分仅用于界面预览。",
        "monthly": monthly,
        "topics": topics,
        "turning_points": [
            {
                "date": messages[0].timestamp[:10],
                "title": "故事从这里被记录",
                "observation": "样本中的第一段对话构成这份报告的起点。",
                "inference": "需要完整模型分析才能判断它对关系走向的意义。",
                "evidence_ids": evidence[:2],
            }
        ],
        "support_moments": [
            {
                "title": "回应彼此的时刻",
                "detail": "本地预览找到了包含支持性词语的消息；深度模式会结合前后语境复核。",
                "evidence_ids": [item.id for item in messages if any(k in item.text for k in ("加油", "辛苦", "抱抱"))][:3] or evidence[:2],
            }
        ],
        "open_loops": [
            {
                "item": "从“下次”“改天”“周末”中核对仍未完成的约定",
                "status": "等待 Seed Evolving 深度分析",
                "evidence_ids": [item.id for item in messages if any(k in item.text for k in ("下次", "改天", "周末"))][:3],
            }
        ],
        "patterns": [
            {
                "title": "从主动联系到回应方式",
                "observation": "本地预览只统计表面词频。",
                "possible_meaning": "模式含义必须结合完整上下文谨慎判断。",
                "evidence_ids": evidence[:3],
            }
        ],
        "closing_letter": "谢谢你，让这一年的许多普通日子有了可以回看的坐标。",
    }
