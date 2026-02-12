import unittest
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor

from edeon_engine.interpret.shap_explainer import explain_model, standardised_coefficients, explain_single

class TestSHAPInterpretability(unittest.TestCase):
    def setUp(self):
        # Create some random training and validation matrices
        np.random.seed(42)
        self.X_train = np.random.normal(size=(20, 6))
        self.y_train = np.random.normal(size=20)
        self.X_val = np.random.normal(size=(5, 6))
        self.feature_names = [f"Descriptor_{i}" for i in range(6)]

    def test_explain_linear_model(self):
        # Ridge model
        model = Ridge()
        model.fit(self.X_train, self.y_train)

        # Run explainer
        explanation = explain_model(
            estimator=model,
            algorithm="ridge",
            model_type="regression",
            X_train=self.X_train,
            X_eval=self.X_val,
            feature_names=self.feature_names
        )

        self.assertEqual(explanation["method"], "linear")
        self.assertIn("shap_values", explanation)
        self.assertIn("linear_coefficients", explanation)
        self.assertEqual(len(explanation["global_importance"]), 6)
        self.assertEqual(len(explanation["beeswarm_data"]), 6 * min(200, len(self.X_val)))
        self.assertEqual(len(explanation["per_compound"]), len(self.X_val))

    def test_explain_tree_model(self):
        # RandomForest model
        model = RandomForestRegressor(n_estimators=5, random_state=42)
        model.fit(self.X_train, self.y_train)

        explanation = explain_model(
            estimator=model,
            algorithm="rf",
            model_type="regression",
            X_train=self.X_train,
            X_eval=self.X_val,
            feature_names=self.feature_names
        )

        self.assertEqual(explanation["method"], "tree")
        self.assertIn("shap_values", explanation)
        self.assertNotIn("linear_coefficients", explanation)
        self.assertEqual(len(explanation["global_importance"]), 6)
        self.assertEqual(len(explanation["per_compound"]), len(self.X_val))

    def test_standardised_coefficients(self):
        model = Ridge()
        model.fit(self.X_train, self.y_train)

        coefs = standardised_coefficients(model, self.X_train, self.feature_names)
        self.assertEqual(len(coefs), 6)
        self.assertIn("name", coefs[0])
        self.assertIn("coef", coefs[0])
        self.assertIn("std_coef", coefs[0])

    def test_explain_single_compound(self):
        model = Ridge()
        model.fit(self.X_train, self.y_train)
        
        X_train_bg = self.X_train[:10]
        
        res = explain_single(
            estimator=model,
            algorithm="ridge",
            model_type="regression",
            X_train_bg=X_train_bg,
            query_smiles="CCO",
            featurizer_selections=[{"id": "descriptors_2d", "params": {}}],
            feature_names=self.feature_names
        )
        
        self.assertIn("expected_value", res)
        self.assertIn("prediction", res)
        self.assertIn("top_features", res)
        self.assertIn("remaining_shap", res)

    def test_atom_maps(self):
        from rdkit import Chem
        from edeon_engine.interpret.atom_maps import compute_morgan_with_bitinfo, project_bits_to_atoms, render_contribution_png
        
        # Test compute_morgan_with_bitinfo
        smiles = ["CCO", "c1ccccc1"]
        fps, bit_infos = compute_morgan_with_bitinfo(smiles, radius=2, n_bits=2048)
        self.assertEqual(fps.shape, (2, 2048))
        self.assertEqual(len(bit_infos), 2)
        
        # Validate that CCO has environment bits set
        cco_info = bit_infos[0]
        self.assertGreater(len(cco_info), 0)
        
        # Test project_bits_to_atoms
        mol = Chem.MolFromSmiles("CCO")
        bit_shap = np.zeros(2048)
        # set some dummy shap weights for bits that are set
        for bit in cco_info.keys():
            if bit < 2048:
                bit_shap[bit] = 0.1
                
        weights = project_bits_to_atoms(mol, cco_info, bit_shap)
        self.assertEqual(len(weights), mol.GetNumAtoms())
        # Weights should be non-zero since we assigned SHAP values to active bits
        self.assertGreater(np.sum(np.abs(weights)), 0.0)
        
        # Test render_contribution_png
        data_uri = render_contribution_png(mol, weights)
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))

if __name__ == '__main__':
    unittest.main()
