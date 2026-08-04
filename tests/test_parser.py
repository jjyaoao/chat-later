import unittest
from pathlib import Path

from relationship_archaeology.parser import parse_chat, serialise_messages
from relationship_archaeology.privacy import redact_messages
from relationship_archaeology.stats import compute_stats


ROOT = Path(__file__).resolve().parent.parent


class ParserTests(unittest.TestCase):
    def test_sample_parses_full_year(self):
        text = (ROOT / "sample_data" / "demo_chat.txt").read_text(encoding="utf-8")
        messages = parse_chat(text)
        self.assertEqual(len(messages), 50)
        self.assertEqual(messages[0].id, "E00001")
        self.assertEqual(messages[-1].id, "E00050")
        self.assertEqual(messages[0].timestamp, "2025-01-03 08:12:00")

    def test_header_body_export_format(self):
        messages = parse_chat("2025-01-01 10:00:00 小林\n新年快乐\n2025-01-01 10:02:00 小周\n你也是")
        self.assertEqual([item.text for item in messages], ["新年快乐", "你也是"])

    def test_multiline_message_is_preserved(self):
        messages = parse_chat(
            "[2025-01-01 10:00] 小林: 第一行\n第二行\n第三行\n"
            "[2025-01-01 10:02] 小周: 收到"
        )
        self.assertEqual(messages[0].text, "第一行\n第二行\n第三行")
        self.assertEqual(messages[1].text, "收到")

    def test_csv_export_with_multiline_content(self):
        text = (
            'timestamp,sender,content\n'
            '2025-01-01 10:00:00,小林,"第一行\n第二行"\n'
            '2025-01-01 10:02:00,小周,收到\n'
        )
        messages = parse_chat(text)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].speaker, "小林")
        self.assertEqual(messages[0].text, "第一行\n第二行")

    def test_csv_with_separate_date_and_time_fields(self):
        text = "date,time,name,message\n2025/01/01,10:00,小林,新年快乐\n"
        messages = parse_chat(text)
        self.assertEqual(messages[0].timestamp, "2025-01-01 10:00:00")

    def test_redaction_and_aliases(self):
        messages = parse_chat("[2025-06-02 12:31] 南星: 13800000000\n[2025-06-02 12:32] 林舟: a@example.com")
        safe, aliases, count = redact_messages(messages, aliases=True)
        self.assertEqual(count, 2)
        self.assertEqual(aliases, {"南星": "参与者A", "林舟": "参与者B"})
        self.assertNotIn("13800000000", serialise_messages(safe))
        self.assertNotIn("a@example.com", serialise_messages(safe))

    def test_stats(self):
        messages = parse_chat("[2025-01-01 23:10] A: one\n[2025-02-01 08:00] B: two")
        stats = compute_stats(messages)
        self.assertEqual(stats["message_count"], 2)
        self.assertEqual(stats["late_night_count"], 1)
        self.assertEqual(stats["monthly_counts"], {"2025-01": 1, "2025-02": 1})
        self.assertEqual(stats["active_days"], 2)
        self.assertEqual(stats["daily_counts"]["2025-01-01"], 1)

    def test_fun_stats_and_word_cloud(self):
        messages = parse_chat(
            "[2025-01-01 10:00] A: 周末去骑车吧\n"
            "[2025-01-01 10:02] B: 好啊周末骑车\n"
            "[2025-01-02 23:10] A: 骑车路线发你了\n"
            "[2025-01-03 08:00] B: 骑车出发"
        )
        stats = compute_stats(messages)
        self.assertEqual(stats["longest_streak_days"], 3)
        self.assertEqual(stats["busiest_day"], "2025-01-01")
        self.assertIn("骑车", {item["text"] for item in stats["word_cloud"]})


if __name__ == "__main__":
    unittest.main()
