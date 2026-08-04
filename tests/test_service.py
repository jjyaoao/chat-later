import os
import unittest
from pathlib import Path
from unittest.mock import patch

from relationship_archaeology.seed_client import (
    SeedClientError,
    _build_responses_payload,
    _extract_json,
    _extract_responses_text,
    _friendly_http_error,
)
from relationship_archaeology.service import _client_for_request, analyse, preview


ROOT = Path(__file__).resolve().parent.parent


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "sample_data" / "demo_chat.txt").read_text(encoding="utf-8")

    def test_local_demo_is_explicit(self):
        with patch.dict(os.environ, {"ARK_API_KEY": ""}, clear=False):
            result = analyse({"text": self.text, "aliases": True, "mode": "deep"})
        self.assertEqual(result["engine"], "local-demo")
        self.assertIn("规则预览", result["stages"])
        self.assertEqual(len(result["report"]["monthly"]), 12)
        self.assertTrue(result["evidence"])

    def test_preview_is_local(self):
        result = preview({"text": self.text, "aliases": True})
        self.assertEqual(result["stats"]["message_count"], 50)
        self.assertEqual(result["privacy"]["redaction_count"], 2)
        self.assertEqual(result["sample"][0]["speaker"], "参与者A")

    def test_short_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "至少需要 5 条"):
            analyse({"text": "[2025-01-01 10:00] A: hi"})

    def test_json_fence_parser(self):
        self.assertEqual(_extract_json("```json\n{\"ok\": true}\n```"), {"ok": True})
        with self.assertRaises(SeedClientError):
            _extract_json("not json")

    def test_responses_payload_translation(self):
        payload = _build_responses_payload(
            [
                {"role": "system", "content": "Only JSON."},
                {"role": "user", "content": "Analyse this."},
            ],
            model="doubao-seed-evolving",
            temperature=0.2,
            max_tokens=12000,
        )
        self.assertEqual(payload["instructions"], "Only JSON.")
        self.assertEqual(payload["input"][0]["content"][0]["type"], "input_text")
        self.assertEqual(payload["max_output_tokens"], 12000)
        self.assertEqual(payload["tool_choice"]["name"], "return_json")

    def test_responses_output_text_extraction(self):
        raw = {
            "output": [
                {"type": "reasoning", "content": []},
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "{\"ok\":"},
                        {"type": "output_text", "text": "true}"},
                    ],
                },
            ]
        }
        self.assertEqual(_extract_responses_text(raw), '{"ok":true}')

    def test_responses_function_arguments_extraction(self):
        raw = {
            "output": [
                {
                    "type": "function_call",
                    "name": "return_json",
                    "arguments": '{"ok":true}',
                }
            ]
        }
        self.assertEqual(_extract_responses_text(raw), '{"ok":true}')

    def test_responses_length_error_is_actionable(self):
        with self.assertRaisesRegex(SeedClientError, "Increase max_output_tokens"):
            _extract_responses_text(
                {
                    "status": "incomplete",
                    "incomplete_details": {"reason": "length"},
                    "output": [{"type": "reasoning", "content": []}],
                }
            )

    def test_safe_experience_limit_error_is_actionable(self):
        message = _friendly_http_error(
            429,
            '{"error":{"code":"SetLimitExceeded"}}',
            "https://ark.cn-beijing.volces.com/api/v3",
            "doubao-seed-evolving",
        )
        self.assertIn("安全体验模式", message)

    def test_ephemeral_user_key_is_fixed_to_official_model_endpoint(self):
        client, mode = _client_for_request({"ark_api_key": "demo-key-123"})
        self.assertEqual(mode, "user-key")
        self.assertEqual(client.api_key, "demo-key-123")
        self.assertEqual(client.base_url, "https://ark.cn-beijing.volces.com/api/v3")
        self.assertEqual(client.model, "doubao-seed-evolving")
        self.assertIsNone(client.cache_dir)

    def test_ephemeral_user_key_rejects_whitespace(self):
        with self.assertRaisesRegex(ValueError, "API Key 格式无效"):
            _client_for_request({"ark_api_key": "bad key"})


if __name__ == "__main__":
    unittest.main()
