import unittest

from scripts.evaluate_report import evaluate
from scripts.generate_long_fixture import generate


class EvaluationTests(unittest.TestCase):
    def test_long_fixture_has_requested_size_and_ground_truth(self):
        chat, truth = generate(200)
        self.assertEqual(len(chat.strip().splitlines()), 200)
        self.assertEqual(truth["message_count"], 200)
        self.assertEqual(len(truth["cases"]), 10)

    def test_cross_event_recall_and_invalid_ids(self):
        result = {
            "engine": "doubao-seed-evolving",
            "stats": {"message_count": 4},
            "report": {
                "turning_points": [
                    {"evidence_ids": ["E00001", "E00004"]},
                    {"evidence_ids": ["E99999"]},
                ]
            },
            "telemetry": [
                {
                    "latency_seconds": 1.25,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                }
            ],
            "analysis_trace": {"audited": True, "audit_changed_report": True},
        }
        truth = {
            "cases": [
                {
                    "id": "case",
                    "label": "test",
                    "earlier": ["E00001"],
                    "later": ["E00004"],
                }
            ]
        }
        evaluation = evaluate(result, truth, {"E00001", "E00004"})
        self.assertEqual(evaluation["cross_event_recall"]["recalled"], 1)
        self.assertEqual(evaluation["evidence_integrity"]["invalid_ids"], ["E99999"])
        self.assertEqual(evaluation["agent_run"]["total_tokens"], 15)

    def test_audit_impact_compares_draft_and_final(self):
        result = {
            "report": {"turning_points": [{"title": "after", "evidence_ids": ["E00001"]}]},
            "analysis_trace": {
                "draft": {
                    "turning_points": [
                        {"title": "before", "evidence_ids": ["E99999"]}
                    ]
                },
                "audited": True,
            },
            "telemetry": [],
        }
        truth = {"cases": []}
        evaluation = evaluate(result, truth, {"E00001"})
        audit = evaluation["audit_impact"]
        self.assertTrue(audit["report_changed"])
        self.assertEqual(audit["invalid_ids_before"], ["E99999"])
        self.assertEqual(audit["invalid_ids_after"], [])
        self.assertEqual(audit["evidence_ids_removed"], ["E99999"])
        self.assertEqual(audit["evidence_ids_added"], ["E00001"])


if __name__ == "__main__":
    unittest.main()
