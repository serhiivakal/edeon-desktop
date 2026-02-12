import unittest
import numpy as np
from sklearn.linear_model import Ridge

# Import modules under test
from edeon_engine.models.curation import curate_dataset
from edeon_engine.models.splitters import split_dataset
from edeon_engine.models.validation import kfold_cv, y_scramble_test
from edeon_engine.models.provenance import _hash_dataset

class TestPhase1(unittest.TestCase):
    def test_curation_canonicalises_and_dedupes(self):
        smiles = ["CCO", "OCC", "CCO"]
        activities = [1.0, 2.0, 3.0]
        res = curate_dataset(smiles, activities, "regression")
        self.assertEqual(res["smiles"], ["CCO"])
        self.assertEqual(res["report"]["n_duplicates_merged"], 2)

    def test_curation_strips_salt(self):
        smiles = ["CC(=O)O.[Na+]"]
        activities = [1.0]
        res = curate_dataset(smiles, activities, "regression")
        self.assertEqual(len(res["smiles"]), 1)
        self.assertTrue("CC(=O)O" in res["smiles"] or "CC(=O)[O-]" in res["smiles"])
        self.assertEqual(res["report"]["n_salts_stripped"], 1)

    def test_curation_rejects_invalid(self):
        smiles = ["NOT_A_SMILES"]
        activities = [1.0]
        res = curate_dataset(smiles, activities, "regression")
        self.assertEqual(len(res["smiles"]), 0)
        self.assertEqual(res["report"]["n_invalid"], 1)

    def test_scaffold_split_groups_disjoint(self):
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold
        smiles = [
            "CC1=CC=CC=C1", "C1=CC=CC=C1", "CCC", "CCO", "CC(C)O",
            "CCCC", "CCCCCC", "CCCCCCCC", "ClC(Cl)Cl", "ClC1=CC=CC=C1",
            "OC1=CC=CC=C1", "O=C(O)C1=CC=CC=C1", "NC1=CC=CC=C1", "CN(C)C",
            "O=S(=O)(O)O", "O=C(O)CC(=O)O", "O=C(O)C(=O)O", "CC(=O)O",
            "C1CCCCC1", "CC1=CC=C(C=C1)C(C)C",
        ]
        X = [[0.0]] * len(smiles)
        y = [1.0] * len(smiles)
        train_idx, test_idx = split_dataset(X, y, smiles, "scaffold", 0.2, 42, "regression")
        
        train_scaffolds = set()
        for idx in train_idx:
            mol = Chem.MolFromSmiles(smiles[idx])
            sc = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) if mol else '__invalid__'
            train_scaffolds.add(sc)
            
        test_scaffolds = set()
        for idx in test_idx:
            mol = Chem.MolFromSmiles(smiles[idx])
            sc = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False) if mol else '__invalid__'
            test_scaffolds.add(sc)
            
        intersection = train_scaffolds.intersection(test_scaffolds)
        self.assertEqual(len(intersection), 0, f"Scaffolds overlap: {intersection}")

    def test_random_split_reproducible(self):
        X = [[0.0]] * 100
        y = [1.0] * 100
        smiles = ["CCO"] * 100
        
        train1, test1 = split_dataset(X, y, smiles, "random", 0.2, 42, "regression")
        train2, test2 = split_dataset(X, y, smiles, "random", 0.2, 42, "regression")
        train3, test3 = split_dataset(X, y, smiles, "random", 0.2, 99, "regression")
        
        self.assertEqual(train1, train2)
        self.assertEqual(test1, test2)
        self.assertNotEqual(train1, train3)

    def test_kfold_cv_returns_k_folds(self):
        X = [[i, i*2, i*3] for i in range(20)]
        y = [float(i) for i in range(20)]
        smiles = ["CCO"] * 20
        k = 5
        config = {"hyperparameters": {}}
        res = kfold_cv(X, y, smiles, k, "random", 42, "regression", "Ridge", config)
        
        folds = [r for r in res if r.get('fold') != 'summary']
        self.assertEqual(len(folds), k)

    def test_yscramble_baseline_low(self):
        rng = np.random.RandomState(42)
        X = rng.normal(size=(30, 5))
        y = rng.normal(size=30)
        
        def model_factory():
            return Ridge(alpha=1.0)
            
        res = y_scramble_test(X, y, model_factory, n_iterations=10, test_size=0.2, random_state=42, model_type="regression")
        self.assertLess(res["scrambled_mean"], 0.2)

    def test_dataset_hash_invariant_to_order(self):
        smiles = ["CCO", "OCC", "CCC"]
        activities = [1.0, 2.0, 3.0]
        
        hash1 = _hash_dataset(smiles, activities)
        
        import random
        rng = random.Random(42)
        zipped = list(zip(smiles, activities))
        rng.shuffle(zipped)
        smiles_shuffled, activities_shuffled = zip(*zipped)
        
        hash2 = _hash_dataset(list(smiles_shuffled), list(activities_shuffled))
        self.assertEqual(hash1, hash2)

if __name__ == "__main__":
    unittest.main()
