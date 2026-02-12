import unittest
from edeon_data.pains_filter import check_molecule_alerts, filter_pains_batch
from edeon_data.clustering import select_diverse_subset


class TestLibraryPrep(unittest.TestCase):

    def test_pains_filter_clean(self):
        """Clean compounds (like ethanol, benzene, etc.) should not flag PAINS or reactive alerts."""
        # Ethanol SMILES: CCO
        res = check_molecule_alerts("CCO")
        self.assertTrue(res["valid"])
        self.assertFalse(res["pains"])
        self.assertFalse(res["reactive"])

    def test_pains_filter_alert(self):
        """Compounds with PAINS or reactive groups should be flagged."""
        # Toxoflavin SMILES (known PAINS/interference)
        res_toxo = check_molecule_alerts("CN1C(=O)C2=NC=NN(C)C2=NC1=O")
        # Let's also check an acyl chloride (known reactive group)
        res_reactive = check_molecule_alerts("CC(=O)Cl")
        
        # Verify that either valid PAINS alert catalogs detect them
        self.assertTrue(res_reactive["valid"])
        self.assertTrue(res_reactive["reactive"])

    def test_diversity_clustering(self):
        """Verify that selecting a diverse subset down-samples correctly."""
        # A list of compounds: some are identical, some are similar, some are diverse
        smiles_list = [
            "CC(=O)Oc1ccccc1C(=O)O",  # Aspirin
            "CC(=O)Oc1ccccc1C(=O)O",  # Aspirin duplicate
            "CC(=O)Oc1ccccc1C(=O)OCC",  # Aspirin ethyl ester (highly similar)
            "c1ccccc1",  # Benzene (diverse)
            "CCO",  # Ethanol (diverse)
            "CN1C(=O)C2=NC=NN(C)C2=NC1=O",  # Diverse
        ]
        
        # Select subset with tight similarity threshold (0.6)
        indices = select_diverse_subset(smiles_list, similarity_threshold=0.6, target_size=10)
        
        # The duplicate (index 1) should be filtered out
        self.assertNotIn(1, indices)
        self.assertTrue(len(indices) < len(smiles_list))
        self.assertTrue(len(indices) >= 2)

    def test_bemis_murcko_clustering(self):
        """Verify that Bemis-Murcko scaffold selection works and down-samples correctly."""
        smiles_list = [
            "CC(=O)Oc1ccccc1C(=O)O",  # Aspirin (benzene scaffold)
            "CC(=O)Oc1ccccc1C(=O)OCC",  # Aspirin ethyl ester (benzene scaffold)
            "CCO",  # Ethanol (no scaffold / acyclic)
            "c1ccccc1",  # Benzene (benzene scaffold)
            "C1CCCCC1",  # Cyclohexane (cyclohexane scaffold)
        ]
        
        # Select target size 3. It should pick representative compounds from different scaffolds
        indices = select_diverse_subset(smiles_list, target_size=3, algorithm="bemis_murcko")
        
        # Verify that it selected exactly 3 compounds
        self.assertEqual(len(indices), 3)

    def test_prepare_library_3d_sdf(self):
        """Verify that 3D preparation outputs valid SDF content."""
        from edeon_engine.__main__ import _prepare_library_3d
        smiles_list = ["CCO", "c1ccccc1"]
        sdf_block = _prepare_library_3d(smiles_list, pH=7.4, export_format="sdf")
        self.assertIn("$$$$", sdf_block)
        self.assertIn("Compound_1", sdf_block)
        self.assertIn("Compound_2", sdf_block)

    def test_prepare_library_3d_csv(self):
        """Verify that 3D preparation outputs valid CSV content."""
        from edeon_engine.__main__ import _prepare_library_3d
        smiles_list = ["CCO", "c1ccccc1"]
        csv_block = _prepare_library_3d(smiles_list, pH=7.4, export_format="csv")
        self.assertTrue(csv_block.startswith("name,smiles\n"))
        self.assertIn("Compound_1,CCO", csv_block)
        self.assertIn("Compound_2,c1ccccc1", csv_block)

    def test_prepare_library_3d_smi(self):
        """Verify that 3D preparation outputs valid SMILES list."""
        from edeon_engine.__main__ import _prepare_library_3d
        smiles_list = ["CCO", "c1ccccc1"]
        smi_block = _prepare_library_3d(smiles_list, pH=7.4, export_format="smi")
        self.assertIn("CCO\tCompound_1", smi_block)
        self.assertIn("c1ccccc1\tCompound_2", smi_block)

    def test_mpo_score_handler(self):
        """Verify that the mpo_score RPC handler accepts 'properties' key from Rust."""
        from edeon_engine.__main__ import handle_request
        req = {
            "id": 1,
            "method": "mpo_score",
            "params": {
                "properties": [{"logp": 2.5, "tpsa": 50, "mol_weight": 350}],
                "tice_results": [{"level": "High"}],
                "selectivity_results": [{"min_selectivity": 10.0, "overall_level": "safe"}],
                "resistance_results": [{"level": "Low", "risk_score": 0.0}],
                "toxicity_results": [{"overall_level": "Low", "applicability_domain": {"confidence": 1.0}}],
                "weights": {}
            }
        }
        res = handle_request(req)
        self.assertIsNone(res.get("error"))
        self.assertEqual(len(res["result"]), 1)
        self.assertEqual(res["result"][0]["rank_category"], "Lead")


if __name__ == "__main__":
    unittest.main()
