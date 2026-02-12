import unittest
from edeon_engine.workflows.contracts import Step, WorkflowSpec, Verdict, WorkflowResult
from edeon_engine.workflows.systemicity import compute_systemicity, compute_systemicity_batch
from edeon_engine.workflows.registry import REGISTRY, list_workflows
from edeon_engine.workflows.verdict import make_confidence_aware_verdict

class TestWorkflowsFramework(unittest.TestCase):

    def test_systemicity_neutral(self):
        """Test systemicity calculation for neutral compound."""
        # log Kow = 1.0, neutral (no pKa)
        res = compute_systemicity(1.0, pka=None, is_acid=False)
        self.assertEqual(res["route"], "xylem")
        self.assertTrue(res["is_estimate"])
        self.assertEqual(res["envelope"]["ad_status"], "in_domain")

    def test_systemicity_acid(self):
        """Test systemicity calculation for weak acid compound."""
        # log Kow = 1.5, pKa = 4.8, is_acid = True (carboxylic acid)
        res = compute_systemicity(1.5, pka=4.8, is_acid=True)
        # Weak acid phloem mobility peaks around log Kow 1.5
        self.assertEqual(res["route"], "phloem")
        self.assertTrue(res["systemicity_index"] > 0.5)

    def test_systemicity_batch(self):
        """Test batch systemicity calculation."""
        compounds = [
            {"logp": 1.5, "smiles": "CC(=O)O"}, # acid
            {"logp": 5.5, "smiles": "CCCCCCCCCCC"} # OOD neutral
        ]
        res = compute_systemicity_batch(compounds)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["route"], "phloem")
        self.assertEqual(res[1]["envelope"]["ad_status"], "out_of_domain")

    def test_registry_discovery(self):
        """Verify the workflows registry returns all 8 workflows."""
        workflows = list_workflows()
        self.assertEqual(len(workflows), 8)
        ids = [wf["id"] for wf in workflows]
        self.assertIn("registration_readiness", ids)
        self.assertIn("pollinator_safety", ids)
        self.assertIn("tp_liability", ids)
        self.assertIn("lead_optimization", ids)
        self.assertIn("hit_triage", ids)
        self.assertIn("comparative_benchmarking", ids)
        self.assertIn("selectivity_optimization", ids)
        self.assertIn("scaffold_hop", ids)

    def test_verdict_showstoppers(self):
        """Verify confidence-aware verdict showstopper rule."""
        # If in-domain and showstopper is triggered -> NO_GO, high confidence
        showstoppers = [{
            "name": "acute mammal toxicity",
            "triggered": True,
            "straddling": False,
            "ad_status": "in_domain",
            "rationale": "Parent compound has high acute mammalian toxicity"
        }]
        verdict = make_confidence_aware_verdict(showstoppers)
        self.assertEqual(verdict.band, "NO_GO")
        self.assertEqual(verdict.confidence, "high")
        self.assertIn("acute mammal toxicity", verdict.driver)

        # If showstopper would trigger but out-of-domain -> CONDITIONAL, low confidence
        showstoppers_ood = [{
            "name": "acute mammal toxicity",
            "triggered": True,
            "straddling": False,
            "ad_status": "out_of_domain",
            "rationale": "Parent compound has high acute mammalian toxicity"
        }]
        verdict_ood = make_confidence_aware_verdict(showstoppers_ood)
        self.assertEqual(verdict_ood.band, "CONDITIONAL")
        self.assertEqual(verdict_ood.confidence, "low")
        self.assertEqual(verdict_ood.driver, "insufficient model coverage — measured data needed")

if __name__ == "__main__":
    unittest.main()
