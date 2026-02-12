"""
Unit tests for Edeon Bottleneck Analyzer (Phase L1).
"""

import unittest
from edeon_bottleneck.desirability import (
    load_profile, compute_desirability, compute_desirability_vector,
)
from edeon_bottleneck.leverage import (
    compute_achievable_targets, compute_leverage, rank_by_leverage,
)
from edeon_bottleneck.uncertainty import (
    assess_reliability, check_ambiguity,
)
from edeon_bottleneck.classify import classify_bottleneck
from edeon_bottleneck.antagonism import compute_tradeoff_matrix
from edeon_bottleneck.attrition import compute_gate_attrition
from edeon_bottleneck.weights import suggest_weights
from edeon_bottleneck.ipc_handlers import handle_analyze, handle_compound, handle_attrition


class TestBottleneckAnalyzer(unittest.TestCase):

    def test_desirability_curves(self):
        profile = load_profile("agrochem_default")
        self.assertIn("fish_lc50", profile["endpoints"])

        # Higher better
        ep_cfg = profile["endpoints"]["fish_lc50"]
        self.assertEqual(compute_desirability(0.05, ep_cfg), 0.0)
        self.assertEqual(compute_desirability(100.0, ep_cfg), 1.0)
        self.assertAlmostEqual(compute_desirability(1.0, ep_cfg), 0.2)

        # Step
        step_cfg = profile["endpoints"]["skin_sens"]
        self.assertEqual(compute_desirability(0.1, step_cfg), 1.0)
        self.assertEqual(compute_desirability(0.9, step_cfg), 0.0)

    def test_leverage_counterfactual(self):
        # 3 compounds, 2 endpoints
        d_vecs = [
            {"fish_lc50": 0.1, "dt50": 0.9},
            {"fish_lc50": 0.2, "dt50": 0.8},
            {"fish_lc50": 0.1, "dt50": 0.85},
        ]
        weights = {"fish_lc50": 0.5, "dt50": 0.5}
        targets = {"fish_lc50": 0.9, "dt50": 0.9}

        lev = compute_leverage(d_vecs, ["fish_lc50", "dt50"], weights, targets)
        self.assertIn("fish_lc50", lev)
        self.assertIn("dt50", lev)
        # fish_lc50 has larger headroom → higher leverage
        self.assertGreater(lev["fish_lc50"]["leverage"], lev["dt50"]["leverage"])

    def test_classification_chemical_vs_epistemic(self):
        # High leverage + in-AD → chemical
        res_chem = classify_bottleneck(
            "fish_lc50", leverage=0.2, headroom=0.5, mean_desirability=0.2,
            reliability="ok", rank_stability=0.9, leverage_ci=(0.15, 0.25),
            n_in_ad=50, fraction_out_of_ad=0.1,
        )
        self.assertEqual(res_chem["kind"], "chemical")
        self.assertEqual(res_chem["recommended_action"], "redesign_structure")

        # Insufficient data → epistemic
        res_epi = classify_bottleneck(
            "fish_lc50", leverage=0.2, headroom=0.5, mean_desirability=0.2,
            reliability="insufficient_data", rank_stability=0.9, leverage_ci=(0.15, 0.25),
            n_in_ad=5, fraction_out_of_ad=0.9,
        )
        self.assertEqual(res_epi["kind"], "epistemic")
        self.assertEqual(res_epi["recommended_action"], "measure_endpoint")

        # Low leverage + headroom → distractor
        res_dis = classify_bottleneck(
            "koc", leverage=0.001, headroom=0.3, mean_desirability=0.5,
            reliability="ok", rank_stability=0.9, leverage_ci=(0.0, 0.002),
            n_in_ad=50, fraction_out_of_ad=0.0,
        )
        self.assertEqual(res_dis["kind"], "distractor")

    def test_tradeoff_matrix(self):
        d_vecs = [
            {"ep1": 0.1, "ep2": 0.9},
            {"ep1": 0.3, "ep2": 0.7},
            {"ep1": 0.5, "ep2": 0.5},
            {"ep1": 0.7, "ep2": 0.3},
            {"ep1": 0.9, "ep2": 0.1},
            {"ep1": 0.4, "ep2": 0.6},
            {"ep1": 0.6, "ep2": 0.4},
            {"ep1": 0.8, "ep2": 0.2},
            {"ep1": 0.2, "ep2": 0.8},
            {"ep1": 0.5, "ep2": 0.5},
        ]
        res = compute_tradeoff_matrix(d_vecs, ["ep1", "ep2"])
        self.assertLess(res["matrix"]["ep1"]["ep2"], -0.9)

    def test_gate_attrition(self):
        gates = [
            {"gate_name": "Standardize", "n_input": 100, "n_passed": 95},
            {"gate_name": "Tice Rules", "n_input": 95, "n_passed": 40},
            {"gate_name": "Selectivity", "n_input": 40, "n_passed": 30},
        ]
        res = compute_gate_attrition(gates)
        self.assertEqual(res["dominant_gate"], "Tice Rules")
        self.assertEqual(res["total_input"], 100)
        self.assertEqual(res["total_output"], 30)

    def test_handle_analyze_end_to_end(self):
        compounds = [
            {
                "id": f"cmp_{i}",
                "endpoints": {
                    "fish_lc50": {"value": 0.1 * i, "ad_status": "in"},
                    "dt50": {"value": 100.0, "ad_status": "in"},
                },
            }
            for i in range(1, 20)
        ]

        res = handle_analyze({
            "compounds": compounds,
            "profile": "agrochem_default",
            "project_id": "proj_123",
        })

        self.assertIn("analysis_id", res)
        self.assertIn("endpoints", res)
        self.assertGreater(len(res["endpoints"]), 0)
        self.assertIn("journal_payload", res)
        self.assertEqual(res["journal_payload"]["decision_kind"], "bottleneck_identified")


if __name__ == "__main__":
    unittest.main()
