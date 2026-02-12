import unittest
from edeon_models.types import ADStatus
from edeon_models.ad.base import ADStrategy
from edeon_models.ad.tanimoto_knn import TanimotoKNN_AD

class TestAD(unittest.TestCase):
    
    def setUp(self):
        # Generate a toy training set of 50 organic molecules (mainly simple alkanes, alcohols, and basic benzenes)
        self.training_smiles = [
            "C", "CC", "CCC", "CCCC", "CCCCC", "CCCCCC", "CCCCCCC", "CCCCCCCC", "CCCCCCCCC", "CCCCCCCCCC",
            "CO", "CCO", "CCCO", "CCCCO", "CCCCCO", "CCCCCCCO", "CCCCCCCCCO",
            "CF", "CCF", "CCCF", "CCCCF", "CCCCCF",
            "c1ccccc1", "Cc1ccccc1", "CCc1ccccc1", "CCCc1ccccc1", "CCCCc1ccccc1",
            "Clc1ccccc1", "Brc1ccccc1", "Ic1ccccc1", "Fc1ccccc1",
            "CC(C)O", "CC(C)C", "CCC(C)C", "CCCC(C)C", "CC(C)CCO",
            "C(=O)O", "CC(=O)O", "CCC(=O)O", "CCCC(=O)O", "CCCCC(=O)O",
            "CCN", "CCCN", "CCCCN", "CCCCCN", "c1ccccc1N",
            "CS", "CCS", "CC(C)S", "c1ccccc1S"
        ]
        
    def test_direct_instantiation_of_base_fails(self):
        """Assert that ADStrategy cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            ADStrategy()
            
    def test_tanimoto_knn_instantiation_and_calibration(self):
        """Assert that TanimotoKNN_AD calibrates threshold bounds automatically."""
        ad = TanimotoKNN_AD(self.training_smiles, k=5)
        
        self.assertIsInstance(ad, ADStrategy)
        self.assertIsInstance(ad.in_threshold, float)
        self.assertIsInstance(ad.out_threshold, float)
        self.assertTrue(ad.in_threshold > 0.0)
        self.assertTrue(ad.in_threshold <= ad.out_threshold)
        self.assertEqual(ad.k, 5)

    def test_in_domain_molecules(self):
        """Assert that close structural analogues are flagged as IN applicability domain."""
        ad = TanimotoKNN_AD(self.training_smiles, k=3)
        
        # Test molecules that are very close analogues of members in the training set
        in_domain_queries = [
            "CCCCCCCO",       # Octanol (exact match or direct chain length extension)
            "CCCCCCCCO",      # Nonanol
            "CCCCCCO",        # Hexanol
            "CCCCC(C)C",      # Branched alkane analogue
            "CCCc1ccccc1CC"   # Substituted benzene analogue
        ]
        
        results = ad.score(in_domain_queries)
        self.assertEqual(len(results), 5)
        
        for status, score in results:
            self.assertEqual(status, ADStatus.IN)
            self.assertIsInstance(score, float)
            self.assertTrue(score <= ad.in_threshold)

    def test_out_of_domain_molecules(self):
        """Assert that complex/out-of-domain query structures are flagged as OUT or BORDERLINE."""
        ad = TanimotoKNN_AD(self.training_smiles, k=3)
        
        # Highly complex, non-organic, or inorganic structures that have very little similarity to simple organic compounds
        out_of_domain_queries = [
            "[Na+].[Cl-]",                             # Table salt
            "[Mg++].[Cl-].[Cl-]",                       # Magnesium chloride
            "[Ca++].[Cl-].[Cl-]",                       # Calcium chloride
            "[K+].[I-]",                               # Potassium iodide
            "[Li+].[F-]"                               # Lithium fluoride
        ]
        
        # To be absolutely sure they are out-of-domain, let's use some highly complex organometallics or fluorinated long structures
        extreme_out_queries = [
            "[Na+].[Cl-]",                             # Table salt
            "[Mg++].[Cl-].[Cl-]",                       # Magnesium chloride
            "[Ca++].[Cl-].[Cl-]",                       # Calcium chloride
            "[K+].[I-]",                               # Potassium iodide
            "[Li+].[F-]"                               # Lithium fluoride
        ]
        
        results = ad.score(extreme_out_queries)
        self.assertEqual(len(results), 5)
        
        for status, score in results:
            # Should be flagged as OUT or BORDERLINE depending on exact similarity
            self.assertIn(status, [ADStatus.OUT, ADStatus.BORDERLINE])
            self.assertIsInstance(score, float)
            self.assertTrue(score > ad.in_threshold)

    def test_invalid_smiles_handling(self):
        """Assert that invalid or un-parseable SMILES strings resolve to ADStatus.UNKNOWN."""
        ad = TanimotoKNN_AD(self.training_smiles, k=5)
        
        invalid_queries = [
            "INVALID_SMILES",
            "C===C",
            "",
            "12345"
        ]
        
        results = ad.score(invalid_queries)
        self.assertEqual(len(results), 4)
        for status, score in results:
            self.assertEqual(status, ADStatus.UNKNOWN)
            self.assertIsNone(score)

if __name__ == "__main__":
    unittest.main()
