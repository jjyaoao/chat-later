from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FILLER = (
    "今天下班路上看到一只橘猫，蹲在便利店门口。",
    "到家啦，晚饭吃得有点晚，你也记得喝水。",
    "刚把今天的事情收尾，明早还有一个会。",
    "天气突然变凉了，出门别忘了带外套。",
    "把刚才说的链接存好了，周末有空再一起看。",
    "午饭那家小店还不错，下次可以换一道菜。",
    "今天进度比预想顺利，晚上准备早点休息。",
    "路上有点堵，我大概晚十分钟到。",
)

SCENARIOS = (
    ("spring_hike", "春天去北山徒步", "2025-01-12 10:00", "等天气暖一点，我们去北山走那条七公里的路线吧。", "2025-03-22 18:40", "北山徒步完成，七公里比想象中轻松，下次还可以走湖边线。"),
    ("blue_vase", "蓝色花瓶约定", "2025-02-03 19:10", "六月搬家时想买那个蓝色花瓶，先记在这里。", "2025-06-08 16:20", "蓝色花瓶已经放到新家窗边了，和二月想的一样。"),
    ("exam_support", "备考与结果", "2025-03-05 22:15", "四月开始备考可能会很忙，希望七月出成绩时我们一起吃饭。", "2025-07-19 12:05", "成绩出来通过了，晚上去兑现三月说的那顿饭。"),
    ("plant_care", "绿萝照看", "2025-04-11 08:30", "出差时能帮我每周给书房绿萝浇一次水吗？", "2025-05-02 20:10", "出差结束，绿萝状态很好，谢谢你三周都有记得浇水。"),
    ("reply_feedback", "回复节奏调整", "2025-05-18 21:00", "忙的时候能不能说一声？我不需要秒回，只是不想一直猜。", "2025-06-02 09:10", "这两周忙的时候提前说一声，确实让我们的沟通轻松多了。"),
    ("autumn_trip", "秋天旅行", "2025-06-21 14:30", "十月想去海边住两天，等排班出来我们一起确认。", "2025-10-04 21:10", "海边旅行第二天，终于把六月写下的计划变成了照片。"),
    ("year_album", "年度相册", "2025-07-07 11:20", "今年年底把每个月各挑一张照片做成小相册吧。", "2025-12-20 18:50", "十二张照片都排好了，年度相册今晚送去印。"),
    ("family_visit", "家人探访后的跟进", "2025-08-09 16:00", "周末去看家人回来可能会有点低落，到时陪我走走。", "2025-09-01 20:00", "今天散步时聊完八月那次探访，心里松了很多。"),
    ("job_interview", "面试到入职", "2025-09-14 23:00", "十一月那场面试我有点没底，明天陪我模拟一下。", "2025-11-22 18:15", "录用邮件到了，九月那次模拟里练的问题真的问到了。"),
    ("new_year_lights", "跨年灯光约定", "2025-11-30 19:30", "今年还去江边看跨年灯光吗？先等值班表确认。", "2025-12-27 12:10", "值班调开了，江边灯光的票也订好了，跨年约定闭环。"),
)


def generate(message_count: int) -> tuple[str, dict]:
    if message_count < 100:
        raise ValueError("message_count must be at least 100")
    entries: list[tuple[datetime, str, str, str | None]] = []
    start = datetime(2025, 1, 1, 8, 0)
    span_minutes = int(timedelta(days=364, hours=14).total_seconds() // 60)
    filler_count = message_count - len(SCENARIOS) * 2
    for index in range(filler_count):
        moment = start + timedelta(minutes=(span_minutes * index) // max(1, filler_count - 1))
        speaker = "林舟" if index % 2 == 0 else "南星"
        text = f"{FILLER[index % len(FILLER)]}（日常片段 {index + 1:05d}）"
        entries.append((moment, speaker, text, None))

    scenario_meta = []
    for case_id, label, earlier_at, earlier_text, later_at, later_text in SCENARIOS:
        entries.append((datetime.strptime(earlier_at, "%Y-%m-%d %H:%M"), "林舟", earlier_text, f"{case_id}:earlier"))
        entries.append((datetime.strptime(later_at, "%Y-%m-%d %H:%M"), "南星", later_text, f"{case_id}:later"))
        scenario_meta.append((case_id, label))

    entries.sort(key=lambda item: (item[0], item[1], item[2]))
    tag_to_id: dict[str, str] = {}
    lines = []
    context_lines = []
    for index, (moment, speaker, text, tag) in enumerate(entries, start=1):
        evidence_id = f"E{index:05d}"
        if tag:
            tag_to_id[tag] = evidence_id
        lines.append(f"[{moment:%Y-%m-%d %H:%M}] {speaker}: {text}")
        alias = "参与者A" if speaker == "林舟" else "参与者B"
        context_lines.append(
            f"{evidence_id}\t{moment:%Y-%m-%d %H:%M:%S}\t{alias}\t{text}"
        )
    chat = "\n".join(lines) + "\n"
    context_chars = len("\n".join(context_lines))
    truth = {
        "description": "合成年度聊天中的 10 条跨月或跨事件证据链。",
        "synthetic": True,
        "message_count": message_count,
        "character_count": len(chat),
        "context_character_count": context_chars,
        "estimated_tokens": round(context_chars / 1.7),
        "token_estimate_note": "粗略字符估算；提交前请用 scripts/count_ark_tokens.py 调用官方分词接口校准。",
        "cases": [
            {
                "id": case_id,
                "label": label,
                "earlier": [tag_to_id[f"{case_id}:earlier"]],
                "later": [tag_to_id[f"{case_id}:later"]],
            }
            for case_id, label in scenario_meta
        ],
    }
    return chat, truth


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic long chat fixture.")
    parser.add_argument("--messages", type=int, default=20000)
    parser.add_argument(
        "--output-chat", type=Path, default=ROOT / "output" / "long_fixture_chat.txt"
    )
    parser.add_argument(
        "--output-truth", type=Path, default=ROOT / "output" / "long_fixture_truth.json"
    )
    args = parser.parse_args()
    chat, truth = generate(args.messages)
    args.output_chat.parent.mkdir(parents=True, exist_ok=True)
    args.output_truth.parent.mkdir(parents=True, exist_ok=True)
    args.output_chat.write_text(chat, encoding="utf-8")
    args.output_truth.write_text(
        json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Messages: {truth['message_count']}")
    print(f"Characters: {truth['character_count']}")
    print(f"Estimated tokens: {truth['estimated_tokens']}")
    print(f"Ground-truth cases: {len(truth['cases'])}")
    print(f"Chat: {args.output_chat.resolve()}")
    print(f"Truth: {args.output_truth.resolve()}")


if __name__ == "__main__":
    main()
