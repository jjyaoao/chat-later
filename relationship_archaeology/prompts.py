from __future__ import annotations

import json


SYSTEM_PROMPT = """你是“关系考古局”的报告 Agent。你分析的是聊天行为与叙事变化，不做心理诊断，不判断人格，不裁决谁对谁错。
所有事实性结论必须引用输入中的证据编号 E00001 这类 ID；证据不足时明确写“无法判断”。将观察、推断和建议分开。输出严格 JSON，不使用 Markdown 代码围栏。"""


SCHEMA = {
    "title": "报告标题",
    "subtitle": "一句克制、具体的总结",
    "overview": "120字以内年度关系叙事",
    "confidence_note": "样本局限与置信说明",
    "monthly": [
        {
            "month": "YYYY-MM",
            "warmth": 0,
            "friction": 0,
            "summary": "当月变化",
            "evidence_ids": ["E00001"],
        }
    ],
    "topics": [
        {"name": "主题", "share": 0, "change": "变化", "evidence_ids": ["E00001"]}
    ],
    "turning_points": [
        {
            "date": "YYYY-MM-DD",
            "title": "事件",
            "observation": "可观察事实",
            "inference": "谨慎推断",
            "evidence_ids": ["E00001"],
        }
    ],
    "support_moments": [
        {"title": "托举时刻", "detail": "发生了什么", "evidence_ids": ["E00001"]}
    ],
    "open_loops": [
        {"item": "尚未闭环的约定", "status": "状态", "evidence_ids": ["E00001"]}
    ],
    "patterns": [
        {
            "title": "互动模式",
            "observation": "观察",
            "possible_meaning": "可能含义",
            "evidence_ids": ["E00001"],
        }
    ],
    "closing_letter": "可分享给对方的一小段年末留言，真诚但不过度煽情",
}


def build_plan_prompt(stats: dict, sample: str) -> str:
    return f"""先为这份聊天记录制定一份具体分析计划。不要开始写最终报告。
数据概况：{json.dumps(stats, ensure_ascii=False)}
首尾抽样：
{sample}

输出 JSON：{{"focus":["重点问题"],"risks":["可能误判"],"checks":["核验动作"]}}"""


def build_analysis_prompt(stats: dict, plan: dict, records: str) -> str:
    return f"""请按照计划分析完整记录，并严格遵守输出结构。

数据概况：{json.dumps(stats, ensure_ascii=False)}
分析计划：{json.dumps(plan, ensure_ascii=False)}
输出结构：{json.dumps(SCHEMA, ensure_ascii=False)}

评分规则：warmth/friction 为 0-100 的叙事辅助指标，不是科学量表；没有该月数据就不要补月。topics 的 share 总和应接近 100。
证据规则：只允许引用输入中真实存在的 E 编号；重要结论至少引用 2 条；不要大段复述原话。

完整记录（制表符分隔：证据ID、时间、说话者、正文）：
{records}"""


def build_audit_prompt(records: str, draft: dict) -> str:
    return f"""审计下面的关系报告。逐项检查证据编号是否存在、结论是否被证据支持、观察与推断是否混淆、是否出现心理诊断或道德裁决。修正问题后返回完整报告 JSON，字段结构保持不变。证据不足的内容删除或降级为“无法判断”。

原始记录：
{records}

待审计报告：
{json.dumps(draft, ensure_ascii=False)}"""

