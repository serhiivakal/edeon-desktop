"""
Tests for the report renderer and analog registry.
"""
import unittest

from edeon_engine.workflows.contracts import WorkflowResult, Verdict
from edeon_engine.workflows.reports.renderer import (
    render_dossier_html,
    TEMPLATE_MAP,
)
from edeon_engine.design.analog_registry import (
    get_generator,
    register_generator,
    ANALOG_GENERATORS,
)


def _make_test_result(workflow_id: str, template_id: str) -> WorkflowResult:
    """Create a minimal WorkflowResult for rendering tests."""
    return WorkflowResult(
        workflow_id=workflow_id,
        per_compound=[{
            "name": "TestCompound",
            "smiles": "CCO",
            "verdict": {
                "band": "GO",
                "driver": "all clear",
                "confidence": "high",
                "rationale": "No issues detected."
            },
            # W1-specific fields
            "scorecard": {
                "criteria": [
                    {"criterion": "Soil persistence", "status": "pass", "evidence": []},
                    {"criterion": "PBT", "status": "likely_showstopper", "evidence": ["LogP > 4.5"]}
                ]
            },
            "tp_count": 3,
            "metabolite_risk": "low",
            "worst_tp": None,
            # W2-specific fields
            "bee_oral_ld50": 15.0,
            "systemicity_index": 0.3,
            "systemicity_route": "contact",
            # W3-specific fields
            "flagged_tps": [
                {"smiles": "CC=O", "probability": 0.8, "route": "metabolic",
                 "liabilities": ["Persistence (DT50: 120d)"], "severity": 0.8}
            ],
            "total_tps": 5,
            # W4-specific fields
            "objective": "selectivity",
            "parent_score": 5.0,
            "analogs": [
                {"smiles": "CCCO", "transformation": "chain extension",
                 "delta": 2.5, "score": 2.0, "is_in_domain": True,
                 "ad_status": "in_domain", "trade_offs": []}
            ],
            # W5-specific fields (mpo_score)
            "mpo_score": 0.78,
            # W6-specific fields
            "comparisons": [
                {
                    "reference_name": "Glyphosate",
                    "reference_use_class": "herbicide",
                    "similarity": 0.65,
                    "axis_comparisons": [
                        {"axis": "logp", "candidate_value": 2.1,
                         "reference_value": -3.2, "delta_pct": 165.6,
                         "assessment": "worse"}
                    ]
                }
            ],
            "better_count": 1, "comparable_count": 2, "worse_count": 1,
            # W7-specific fields
            "parent_min_margin": 8.5,
            "limiting_organism": "Honeybee",
            "ranked_analogs": [
                {"smiles": "CCCO", "transformation": "chain ext",
                 "new_min_margin": 12.0, "lift": 3.5,
                 "ad_status": "in_domain", "collapsed_window": False}
            ],
            # W8-specific fields
            "ranked_hops": [
                {"smiles": "c1ccccc1", "transformation": "aromatize",
                 "novelty_distance": 0.6, "profile_match": 0.85,
                 "composite_score": 0.72, "ad_status": "in_domain"}
            ],
        }],
        overall=Verdict(
            band="GO",
            driver="all clear",
            confidence="high",
            rationale="No issues detected."
        ),
        sections={
            "summary": "Test summary.",
            "disclaimer": "IN-SILICO SCREENING ONLY.",
            "attrition": [
                {"stage": "likeness", "in": 10, "out": 8, "dropped": 2, "reason": "Low likeness"},
                {"stage": "pains", "in": 8, "out": 7, "dropped": 1, "reason": "PAINS flagged"}
            ],
            "legal_disclaimer": "STRUCTURAL HEURISTIC ONLY — not a patentability opinion."
        },
        warnings=["Test warning"],
        provenance={"engine": "edeon_engine_v1.0"}
    )


class TestReportRenderer(unittest.TestCase):

    def test_all_templates_render(self):
        """Every registered template should render without errors."""
        for template_id in TEMPLATE_MAP:
            # Map template_id to a workflow_id
            wf_id_map = {
                "w1_dossier": "registration_readiness",
                "w2_pollinator": "pollinator_safety",
                "w3_tp_report": "tp_liability",
                "w4_opt_proposal": "lead_optimization",
                "w5_shortlist": "hit_triage",
                "w6_comparison": "comparative_benchmarking",
                "w7_window": "selectivity_optimization",
                "w8_scaffold_hop": "scaffold_hop",
            }
            wf_id = wf_id_map.get(template_id, "test")
            result = _make_test_result(wf_id, template_id)
            
            with self.subTest(template_id=template_id):
                html = render_dossier_html(result, template_id)
                # Basic sanity checks
                self.assertIn("<!DOCTYPE html>", html)
                self.assertIn("Edeon", html)
                self.assertIn("TestCompound", html)
                self.assertIn("IN-SILICO", html)
                # Should contain the verdict banner
                self.assertIn("band-go", html)
    
    def test_template_contains_workflow_content(self):
        """W1 template should render scorecard, W3 should render flagged TPs."""
        # W1 scorecard
        result = _make_test_result("registration_readiness", "w1_dossier")
        html = render_dossier_html(result, "w1_dossier")
        self.assertIn("Soil persistence", html)
        self.assertIn("SHOWSTOPPER", html)
        
        # W3 flagged TPs
        result3 = _make_test_result("tp_liability", "w3_tp_report")
        html3 = render_dossier_html(result3, "w3_tp_report")
        self.assertIn("CC=O", html3)
        self.assertIn("Persistence", html3)
    
    def test_unknown_template_raises(self):
        """Requesting an unknown template ID should raise ValueError."""
        result = _make_test_result("test", "nonexistent")
        with self.assertRaises(ValueError):
            render_dossier_html(result, "nonexistent")


class TestAnalogRegistry(unittest.TestCase):
    
    def test_get_default_generator(self):
        """Default strategy should return a callable."""
        gen = get_generator("default")
        self.assertTrue(callable(gen))
    
    def test_get_bioisostere_generator(self):
        """bioisostere_only should be registered."""
        gen = get_generator("bioisostere_only")
        self.assertTrue(callable(gen))
    
    def test_unknown_strategy_falls_back(self):
        """Unknown strategy should fall back to default without crashing."""
        gen = get_generator("nonexistent_strategy")
        self.assertTrue(callable(gen))
        # Should be the same as default
        self.assertEqual(gen, get_generator("default"))
    
    def test_register_custom_generator(self):
        """Custom generators can be registered at runtime."""
        def my_custom_gen(smiles, target):
            return [{"smiles": "C", "rule_name": "test", "description": "custom"}]
        
        register_generator("custom_test", my_custom_gen)
        gen = get_generator("custom_test")
        self.assertEqual(gen, my_custom_gen)
        
        # Verify it works
        result = gen("CCO", "persistence")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["smiles"], "C")
        
        # Clean up
        del ANALOG_GENERATORS["custom_test"]


if __name__ == "__main__":
    unittest.main()
