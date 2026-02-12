"""
Unit tests for Edeon Decision Journal Payloads & Analytics (Phase M).
"""

import unittest
from edeon_engine.journal_payload import (
    build_summary, build_why_not, build_rationale,
    build_alternatives, build_confidence, build_provenance,
    build_journal_payload,
)


class TestJournalPayloads(unittest.TestCase):

    def test_summary_templates(self):
        s1 = build_summary(
            "workflow_verdict",
            workflow_name="Resistance-Aware",
            verdict="Promote",
            n_compounds=50,
            n_passed=12,
        )
        self.assertIn("Resistance-Aware", s1)
        self.assertIn("Promote", s1)
        self.assertIn("12 passed", s1)

        s2 = build_summary(
            "bottleneck_identified",
            top_endpoint="fish_lc50",
            kind="chemical",
            leverage=0.2345,
        )
        self.assertIn("fish_lc50", s2)
        self.assertIn("chemical", s2)

    def test_why_not_templates(self):
        wn = build_why_not("lower_score", label="Compound-B", score=4.2, winner_score=7.8)
        self.assertIn("Compound-B not chosen", wn)
        self.assertIn("4.20 vs winner 7.80", wn)

    def test_build_journal_payload(self):
        payload = build_journal_payload(
            decision_kind="model_deployed",
            subject_type="model",
            subject_id="mod_456",
            summary_kwargs={
                "model_name": "RF-Ecotox",
                "endpoint": "fish_lc50",
                "tier": 2,
            },
            provenance=build_provenance("params_hash_123"),
            rationale=build_rationale(
                drivers=[{"factor": "r2", "value": 0.85}],
            ),
        )

        self.assertEqual(payload["decision_kind"], "model_deployed")
        self.assertEqual(payload["subject_type"], "model")
        self.assertEqual(payload["subject_id"], "mod_456")
        self.assertIn("RF-Ecotox", payload["summary"])
        self.assertEqual(payload["provenance"]["params_hash"], "params_hash_123")


if __name__ == "__main__":
    unittest.main()
