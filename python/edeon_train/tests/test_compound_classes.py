import unittest
from edeon_train.shared.compound_classes import tag_compound_classes

class TestCompoundClasses(unittest.TestCase):
    def test_known_pesticides(self):
        # 1. Imidacloprid (neonicotinoid)
        imidacloprid_smiles = "C1C(N(C2=C1C=C(C=C2)Cl)C(=N[N+](=O)[O-])N)"
        self.assertIn("neonicotinoid", tag_compound_classes(imidacloprid_smiles))
        
        # 2. Tebuconazole (triazole fungicide)
        tebuconazole_smiles = "CC(C)(C)C(O)(CN1C=NC=N1)CC2=CC=C(C=C2)Cl"
        self.assertIn("triazole", tag_compound_classes(tebuconazole_smiles))
        
        # 3. Carbaryl (carbamate insecticide)
        carbaryl_smiles = "CN(=O)=CO"  # simple carbamate representation or standard:
        carbaryl_smiles_real = "CNC(=O)OC1=CC=CC2=CC=CC=C21"
        self.assertIn("carbamate", tag_compound_classes(carbaryl_smiles_real))
        
        # 4. Azoxystrobin (strobilurin fungicide)
        azoxystrobin_smiles = "CO/C=C(\\C(=O)OC)/C1=C(OC2=NC(=NC=C2)OC3=CC=C(C=C3)C#N)C=CC=C1"
        self.assertIn("strobilurin", tag_compound_classes(azoxystrobin_smiles))
        
        # 5. Glyphosate (unclassified)
        glyphosate_smiles = "C(C(=O)O)NCP(=O)(O)O"
        self.assertEqual(tag_compound_classes(glyphosate_smiles), ["unclassified"])
        
        # 6. Invalid SMILES
        self.assertEqual(tag_compound_classes("INVALID"), ["unclassified"])

if __name__ == "__main__":
    unittest.main()
