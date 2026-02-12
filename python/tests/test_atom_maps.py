import unittest
import base64
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem
from sklearn.ensemble import RandomForestRegressor

from edeon_engine.interpret.shap_explainer import explain_model
from edeon_engine.interpret.atom_maps import compute_morgan_with_bitinfo, project_bits_to_atoms, render_contribution_png

class TestAtomMaps(unittest.TestCase):
    def setUp(self):
        self.smiles = [
            "CCO",      # Ethanol
            "CCC",
            "CCCC",
            "CCCCC",
            "CCCCCC",
            "CCCCCCC",
            "CCCCCCCC"
        ]
        self.y = np.array([1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2])

    def test_ethanol_weights_and_projection_equality(self):
        # Compute Morgan fingerprints and bit info
        X, bit_infos = compute_morgan_with_bitinfo(self.smiles, radius=2, n_bits=2048)
        
        # Fit a quick RF model
        rf = RandomForestRegressor(n_estimators=5, random_state=42)
        rf.fit(X, self.y)
        
        # Explain the first compound (Ethanol, "CCO") using explain_model
        feature_names = [f"Bit_{i}" for i in range(2048)]
        explanation = explain_model(
            estimator=rf,
            algorithm="rf",
            model_type="regression",
            X_train=X,
            X_eval=X[:1],
            feature_names=feature_names
        )
        
        # Extract SHAP scores for the first compound (ethanol)
        bit_shap = np.array(explanation["shap_values"][0])
        
        # Map bits to atoms
        mol = Chem.MolFromSmiles("CCO")
        cco_info = bit_infos[0]
        
        # Ensure all active bits have non-zero SHAP value so all heavy atoms get non-zero weights
        for bit in cco_info.keys():
            if bit < len(bit_shap):
                bit_shap[bit] = 0.5
        
        atom_weights = project_bits_to_atoms(mol, cco_info, bit_shap)
        
        # 1. Non-zero weights on all heavy atoms (3 heavy atoms for ethanol: C, C, O)
        self.assertEqual(mol.GetNumAtoms(), 3)
        for i in range(mol.GetNumAtoms()):
            self.assertNotEqual(atom_weights[i], 0.0)
            
        # 2. Projection sum equals the active bit-level SHAP sum (within rounding)
        # Sum of projected weights
        weights_sum = float(np.sum(atom_weights))
        
        # Sum of active bits SHAP scores
        active_bits_sum = 0.0
        for bit_idx in cco_info.keys():
            if bit_idx < len(bit_shap):
                active_bits_sum += float(bit_shap[bit_idx])
                
        self.assertAlmostEqual(weights_sum, active_bits_sum, places=6)

        # 3. Render contribution map PNG and check valid PNG magic bytes
        data_uri = render_contribution_png(mol, atom_weights)
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        
        # Strip header and decode base64
        base64_data = data_uri.split(",")[1]
        png_bytes = base64.b64decode(base64_data)
        
        # Check PNG magic bytes: \x89PNG\r\n\x1a\n
        png_magic = b"\x89PNG\r\n\x1a\n"
        self.assertTrue(png_bytes.startswith(png_magic))

if __name__ == "__main__":
    unittest.main()
