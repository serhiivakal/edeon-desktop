import unittest
from edeon_engine.reference.reference_library import reference_lookup
from edeon_engine.workflows.contracts import Step, WorkflowSpec, Verdict, WorkflowResult
from edeon_engine.workflows.runner import run_workflow
from edeon_engine.workflows.objectives import maximin_selectivity, scaffold_novelty, get_bemis_murcko_scaffold
from edeon_engine.workflows.registry import REGISTRY

class TestTier2Workflows(unittest.TestCase):

    def test_reference_lookup(self):
        """Test looking up reference actives."""
        # Query by name
        res = reference_lookup("name", "Glyphosate")
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["active"]["name"], "Glyphosate")
        
        # Query by use class
        res = reference_lookup("use_class", "Fungicide")
        self.assertGreater(len(res), 0)
        self.assertEqual(res[0]["active"]["use_class"], "Fungicide")
        
        # Query by similarity
        res = reference_lookup("similarity", "C(C(=O)O)NCP(=O)(O)O", limit=2)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["active"]["id"], "glyphosate")
        self.assertAlmostEqual(res[0]["similarity"], 1.0)

    def test_maximin_selectivity(self):
        """Test maximin selectivity calculation."""
        lead_sel = {
            "profiles": [
                {"organism": "Honeybee", "selectivity_index": 5.0, "ad_status": "in"},
                {"organism": "Mammal", "selectivity_index": 20.0, "ad_status": "in"},
            ],
            "min_selectivity": 5.0
        }
        
        # Analog 1: improves bee selectivity, does not collapse mammal
        analog_sel_1 = {
            "profiles": [
                {"organism": "Honeybee", "selectivity_index": 8.0, "ad_status": "in"},
                {"organism": "Mammal", "selectivity_index": 22.0, "ad_status": "in"},
            ],
            "min_selectivity": 8.0
        }
        
        # Analog 2: improves bee but collapses mammal below threshold (Mammal threshold is 10.0)
        analog_sel_2 = {
            "profiles": [
                {"organism": "Honeybee", "selectivity_index": 12.0, "ad_status": "in"},
                {"organism": "Mammal", "selectivity_index": 5.0, "ad_status": "in"}, # below 10.0!
            ],
            "min_selectivity": 5.0
        }
        
        res_1 = maximin_selectivity(analog_sel_1, lead_sel)
        self.assertEqual(res_1["lift"], 3.0)
        self.assertFalse(res_1["collapses_margin"])
        self.assertGreater(res_1["final_rank_score"], 0)
        
        res_2 = maximin_selectivity(analog_sel_2, lead_sel)
        self.assertTrue(res_2["collapses_margin"])
        self.assertLess(res_2["final_rank_score"], -500)

    def test_scaffold_novelty(self):
        """Test scaffold novelty and Bemis-Murcko comparison."""
        lead = "CC1=CC=CC=C1" # Toluene (scaffold is benzene)
        cand_same = "CC1=CC=CC=C1Cl" # Cl-toluene (scaffold is benzene)
        cand_diff = "C1CCCCC1" # Cyclohexane (scaffold is cyclohexane)
        
        res_same = scaffold_novelty(cand_same, lead)
        self.assertFalse(res_same["is_novel_scaffold"])
        
        res_diff = scaffold_novelty(cand_diff, lead)
        self.assertTrue(res_diff["is_novel_scaffold"])
        self.assertGreater(res_diff["novelty"], 0.3)
        self.assertGreater(res_diff["min_ref_distance"], 0.0)

    def test_w5_triage_execution(self):
        """Test running W5 Hit-to-Shortlist Triage."""
        input_data = {
            "smiles": [
                "C(C(=O)O)NCP(=O)(O)O", # Glyphosate (herbicide-like, survives)
                "CCCCCCCCCCCCCCCCCCCCC", # OOD/Low likeness (gated)
                "C1CN(C(=N[N+](=O)[O-])N1)CC2=CN=C(C=C2)Cl" # Imidacloprid (insecticide-like, survives)
            ]
        }
        params = {"shortlist_size": 2}
        result = run_workflow("hit_triage", input_data, params)
        
        self.assertEqual(result.workflow_id, "hit_triage")
        self.assertIn("attrition", result.sections)
        self.assertGreater(len(result.sections["attrition"]), 0)
        
        # Test attrition waterfall entries
        attrition = result.sections["attrition"]
        self.assertEqual(attrition[0]["stage"], "pesticide_likeness")
        # Gated count check
        self.assertGreater(attrition[0]["dropped"], 0)
        
        # Shortlist checks
        self.assertGreater(len(result.per_compound), 0)
        # Glyphosate and Imidacloprid should be priority/consider, long chain should be deprioritized
        tiers = {c["smiles"]: c["tier"] for c in result.per_compound}
        self.assertIn("O=C(O)CNCP(=O)(O)O", tiers)
        self.assertIn("CCCCCCCCCCCCCCCCCCCCC", tiers)
        self.assertEqual(tiers["CCCCCCCCCCCCCCCCCCCCC"], "deprioritized")

    def test_w6_benchmarking_execution(self):
        """Test running W6 Comparative Benchmarking."""
        input_data = {"smiles": ["C(C(=O)O)NCP(=O)(O)O"]}
        params = {
            "reference_by": "name",
            "reference_query": "Glyphosate",
            "reference_limit": 1
        }
        result = run_workflow("comparative_benchmarking", input_data, params)
        
        self.assertEqual(result.workflow_id, "comparative_benchmarking")
        self.assertGreater(len(result.per_compound), 0)
        comp = result.per_compound[0]
        self.assertIn("comparisons", comp)
        self.assertEqual(comp["comparisons"][0]["reference_name"], "Glyphosate")

    def test_w7_selectivity_window_execution(self):
        """Test running W7 Selectivity Window Optimization."""
        input_data = {"smiles": ["C(C(=O)O)NCP(=O)(O)O"]}
        params = {"n_analogs": 2}
        result = run_workflow("selectivity_optimization", input_data, params)
        
        self.assertEqual(result.workflow_id, "selectivity_optimization")
        self.assertGreater(len(result.per_compound), 0)
        self.assertIn("analogs", result.per_compound[0])

    def test_w8_scaffold_hop_execution(self):
        """Test running W8 Scaffold-Hop Explorer."""
        input_data = {"smiles": ["CC1=CC=CC=C1"]}
        params = {"min_novelty_distance": 0.1, "n_analogs": 2}
        result = run_workflow("scaffold_hop", input_data, params)
        
        self.assertEqual(result.workflow_id, "scaffold_hop")
        self.assertGreater(len(result.per_compound), 0)
        self.assertIn("analogs", result.per_compound[0])
        # Check disclaimer exists
        self.assertIn("legal_disclaimer", result.sections)
        self.assertIn("STRUCTURAL HEURISTIC ONLY", result.sections["legal_disclaimer"])

    def test_w1_registration_execution(self):
        """Test running W1 Registration Readiness Pre-Screen."""
        input_data = {"smiles": ["C(C(=O)O)NCP(=O)(O)O"]}  # Glyphosate
        result = run_workflow("registration_readiness", input_data)
        
        self.assertEqual(result.workflow_id, "registration_readiness")
        self.assertGreater(len(result.per_compound), 0)
        comp = result.per_compound[0]
        # Must have verdict with required fields
        self.assertIn("verdict", comp)
        self.assertIn("band", comp["verdict"])
        self.assertIn("confidence", comp["verdict"])
        self.assertIn("rationale", comp["verdict"])
        # Must have scorecard and metabolite risk
        self.assertIn("scorecard", comp)
        self.assertIn("metabolite_risk", comp)
        # Overall verdict must not be None
        self.assertIsNotNone(result.overall)
        self.assertIn(result.overall.band, ["GO", "NO_GO", "CONDITIONAL"])
        # Disclaimer must be present
        self.assertIn("disclaimer", result.sections)
        self.assertIn("IN-SILICO", result.sections["disclaimer"])
        
    def test_w1_aggregator_showstopper_logic(self):
        """Test W1 aggregator: confidence-aware verdict for showstoppers."""
        from edeon_engine.workflows.w1_registration import w1_aggregator
        
        # Simulate step outputs with a triggered showstopper (in-domain)
        step_outputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Ethanol"}],
            "environmental_fate": [{"dt50_soil": {"value": 100, "ad_status": "in_domain"}}],
            "selectivity": [{"profiles": [], "min_selectivity": 10.0}],
            "transformation_products": [{"result": []}],
            "tp_registration_risk": [],
            "registration_risk": [{
                "criteria": [
                    {"criterion": "Soil persistence", "status": "likely_showstopper", "evidence": ["DT50 > 90d"]},
                    {"criterion": "Groundwater contamination", "status": "pass", "evidence": []}
                ]
            }]
        }
        result = w1_aggregator(step_outputs, {"tp_probability_cutoff": 0.1})
        self.assertEqual(result.workflow_id, "registration_readiness")
        comp = result.per_compound[0]
        # Should trigger NO_GO because of in-domain showstopper
        self.assertEqual(comp["verdict"]["band"], "NO_GO")
        self.assertIn("high", comp["verdict"]["confidence"])
        
    def test_w2_pollinator_execution(self):
        """Test running W2 Pollinator Safety Screen."""
        # Imidacloprid - known bee-toxic neonicotinoid
        input_data = {"smiles": ["C1CN(C(=N[N+](=O)[O-])N1)CC2=CN=C(C=C2)Cl"]}
        result = run_workflow("pollinator_safety", input_data)
        
        self.assertEqual(result.workflow_id, "pollinator_safety")
        self.assertGreater(len(result.per_compound), 0)
        comp = result.per_compound[0]
        self.assertIn("verdict", comp)
        self.assertIn("bee_oral_ld50", comp)
        self.assertIn("systemicity_index", comp)
        self.assertIn("systemicity_route", comp)
        # Overall verdict must exist
        self.assertIsNotNone(result.overall)
        # Verdict band should be one of the valid risk levels
        self.assertIn(comp["verdict"]["band"], ["High", "Med", "Low"])
        
    def test_w2_aggregator_risk_matrix(self):
        """Test W2 aggregator: risk matrix categorization."""
        from edeon_engine.workflows.w2_pollinator import w2_aggregator
        
        # High tox + high systemicity -> High risk
        step_outputs_high = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "TestComp"}],
            "selectivity": [{"profiles": [
                {"organism": "Honeybee", "selectivity_index": 1.0, "ad_status": "in"}
            ]}],
            "systemicity": [{"systemicity_index": 0.7, "route": "xylem", "envelope": {"ad_status": "in_domain"}}]
        }
        result_high = w2_aggregator(step_outputs_high, {})
        self.assertEqual(result_high.per_compound[0]["verdict"]["band"], "High")
        
        # Low tox + low systemicity -> Low risk
        step_outputs_low = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "SafeComp"}],
            "selectivity": [{"profiles": [
                {"organism": "Honeybee", "selectivity_index": 20.0, "ad_status": "in"}
            ]}],
            "systemicity": [{"systemicity_index": 0.1, "route": "contact", "envelope": {"ad_status": "in_domain"}}]
        }
        result_low = w2_aggregator(step_outputs_low, {})
        self.assertEqual(result_low.per_compound[0]["verdict"]["band"], "Low")
        
    def test_w3_tp_liability_execution(self):
        """Test running W3 Transformation-Product Liability Sweep."""
        input_data = {"smiles": ["C(C(=O)O)NCP(=O)(O)O"]}  # Glyphosate
        result = run_workflow("tp_liability", input_data)
        
        self.assertEqual(result.workflow_id, "tp_liability")
        self.assertGreater(len(result.per_compound), 0)
        comp = result.per_compound[0]
        self.assertIn("verdict", comp)
        self.assertIn("flagged_tps", comp)
        self.assertIn("total_tps", comp)
        # Overall verdict must exist
        self.assertIsNotNone(result.overall)
        # Confidence should NOT be hardcoded to "high" anymore — it should
        # reflect the AD status of TP predictions
        self.assertIn(comp["verdict"]["confidence"], ["high", "moderate", "low"])
        
    def test_w3_aggregator_confidence_from_ad(self):
        """Test W3 aggregator: confidence is derived from AD status, not hardcoded."""
        from edeon_engine.workflows.w3_tp_liability import w3_aggregator
        
        # Simulate TPs with out-of-domain predictions
        step_outputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Parent"}],
            "environmental_fate": [{"dt50_soil": {"value": 30}, "koc": {"value": 500}}],
            "selectivity": [{"min_selectivity": 10.0}],
            "transformation_products": [{"result": [
                {"smiles": "CC=O", "probability": 0.8, "route": "metabolic", "rule": "oxidation"}
            ]}],
            "tp_standardize": [{"canonical": "CC=O", "valid": True, "original": "CC=O"}],
            "tp_fate": [{"dt50_soil": {"value": 200, "ad_status": "out_of_domain"}, "koc": {"value": 50, "ad_status": "out_of_domain"}}],
            "tp_selectivity": [{"min_selectivity": 2.0}]
        }
        result = w3_aggregator(step_outputs, {"tp_probability_cutoff": 0.1})
        comp = result.per_compound[0]
        # With OOD fate predictions, confidence should be downgraded from "high"
        self.assertIn(comp["verdict"]["confidence"], ["moderate", "low"])
        
    def test_w4_lead_opt_execution(self):
        """Test running W4 Lead-Optimization Cycle."""
        input_data = {"smiles": ["C(C(=O)O)NCP(=O)(O)O"]}  # Glyphosate
        params = {"n_analogs": 3}
        result = run_workflow("lead_optimization", input_data, params)
        
        self.assertEqual(result.workflow_id, "lead_optimization")
        self.assertGreater(len(result.per_compound), 0)
        comp = result.per_compound[0]
        self.assertIn("objective", comp)
        self.assertIn("analogs", comp)
        # The overall verdict should now be populated (fixed from None)
        self.assertIsNotNone(result.overall)
        self.assertIn(result.overall.band, ["GO", "NO_GO", "CONDITIONAL"])
        
    def test_w4_aggregator_verdict_populated(self):
        """Test W4 aggregator: overall verdict is no longer None."""
        from edeon_engine.workflows.w4_lead_opt import w4_aggregator
        
        # Simulate outputs with analogs that improve selectivity
        step_outputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Lead"}],
            "environmental_fate": [{"dt50_soil": {"value": 30}}],
            "selectivity": [{"min_selectivity": 5.0}],
            "suggest_analogs": [{"result": [
                {"smiles": "CCCO", "transformation": "chain extension"}
            ]}],
            "analog_standardize": [{"canonical": "CCCO", "valid": True, "original": "CCCO"}],
            "analog_fate": [{"dt50_soil": {"value": 25}}],
            "analog_selectivity": [{"min_selectivity": 8.0}]
        }
        result = w4_aggregator(step_outputs, {"objective": "selectivity", "n_analogs": 5})
        # Overall verdict must exist
        self.assertIsNotNone(result.overall)
        self.assertIn(result.overall.band, ["GO", "NO_GO", "CONDITIONAL"])
        # Check compound-level result has analogs
        self.assertGreater(len(result.per_compound[0]["analogs"]), 0)
        
    def test_w4_aggregator_no_analogs_verdict(self):
        """Test W4 aggregator: returns NO_GO when no analogs are generated."""
        from edeon_engine.workflows.w4_lead_opt import w4_aggregator
        
        step_outputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Lead"}],
            "environmental_fate": [{}],
            "selectivity": [{"min_selectivity": 5.0}],
            "suggest_analogs": [{"result": []}],
            "analog_standardize": [],
            "analog_fate": [],
            "analog_selectivity": []
        }
        result = w4_aggregator(step_outputs, {"objective": "selectivity", "n_analogs": 5})
        self.assertIsNotNone(result.overall)
        self.assertEqual(result.overall.band, "NO_GO")
        self.assertIn("No analogs", result.overall.driver)

    def test_aggregators_robustness_with_gaps(self):
        """Verify aggregators can handle gaps/failures in analog/metabolite steps without throwing exceptions."""
        from edeon_engine.workflows.w3_tp_liability import w3_aggregator
        from edeon_engine.workflows.w4_lead_opt import w4_aggregator
        from edeon_engine.workflows.w7_selectivity_window import w7_aggregator
        from edeon_engine.workflows.w8_scaffold_hop import w8_aggregator

        # W3 with gaps
        w3_inputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Parent"}],
            "environmental_fate": [{"dt50_soil": {"value": 30}}],
            "selectivity": [{"min_selectivity": 5.0}],
            "transformation_products": [{"result": [{"smiles": "CC=O", "probability": 0.8}]}],
            "tp_standardize": None,
            "tp_fate": [],
            "tp_selectivity": None
        }
        res3 = w3_aggregator(w3_inputs, {"tp_probability_cutoff": 0.1})
        self.assertEqual(len(res3.per_compound), 1)

        # W4 with gaps
        w4_inputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Parent"}],
            "environmental_fate": [{"dt50_soil": {"value": 30}}],
            "selectivity": [{"min_selectivity": 5.0}],
            "suggest_analogs": [{"result": [{"smiles": "CCCO", "transformation": "chain ext"}]}],
            "analog_standardize": [{"canonical": "CCCO", "valid": False, "original": "CCCO"}],
            "analog_fate": [{"dt50_soil": {"value": 25}, "original": "CCCO"}],
            "analog_selectivity": []
        }
        res4 = w4_aggregator(w4_inputs, {"objective": "selectivity", "n_analogs": 5})
        self.assertEqual(len(res4.per_compound), 1)

        # W7 with gaps
        w7_inputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Parent"}],
            "selectivity": [{"min_selectivity": 5.0}],
            "suggest_analogs": [{"result": [{"smiles": "CCCO"}]}],
            "analog_standardize": [],
            "analog_selectivity": []
        }
        res7 = w7_aggregator(w7_inputs, {"penalize_ood": True})
        self.assertEqual(len(res7.per_compound), 1)

        # W8 with gaps
        w8_inputs = {
            "standardize": [{"canonical": "CCO", "valid": True, "name": "Parent"}],
            "selectivity": [{"min_selectivity": 5.0}],
            "environmental_fate": [{"dt50_soil": {"value": 30}}],
            "suggest_analogs": [{"result": [{"smiles": "CCCO"}]}],
            "analog_standardize": [],
            "analog_selectivity": [],
            "analog_fate": []
        }
        res8 = w8_aggregator(w8_inputs, {"min_novelty_distance": 0.2})
        self.assertEqual(len(res8.per_compound), 1)

    def test_registry_completeness(self):
        """Verify all 8 workflows are registered and have required fields."""
        expected_ids = [
            "registration_readiness", "pollinator_safety", "tp_liability",
            "lead_optimization", "hit_triage", "comparative_benchmarking",
            "selectivity_optimization", "scaffold_hop"
        ]
        for wf_id in expected_ids:
            self.assertIn(wf_id, REGISTRY, f"Workflow '{wf_id}' not found in registry")
            spec = REGISTRY[wf_id]
            self.assertIsNotNone(spec.name, f"{wf_id} missing name")
            self.assertIsNotNone(spec.aggregator, f"{wf_id} missing aggregator")
            self.assertGreater(len(spec.steps), 0, f"{wf_id} has no steps")
            self.assertIsNotNone(spec.report_template, f"{wf_id} missing report_template")

if __name__ == "__main__":
    unittest.main()
