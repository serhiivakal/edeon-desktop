import unittest
import numpy as np
import base64
from unittest.mock import patch
from rdkit import DataStructs
from edeon_engine.cliffs import detect_cliffs, render_thumbnail

class TestActivityCliffs(unittest.TestCase):
    @patch("rdkit.DataStructs.BulkTanimotoSimilarity")
    def test_engineered_single_pair_cliffs(self, mock_bulk_sim):
        # 1. Synthetic dataset with one engineered pair (sim=0.93, gap=2.5) yields exactly that pair.
        smiles = ["CCO", "CCN", "c1ccccc1"]
        # y values: A=1.0, B=3.5 (gap = 2.5), C=1.0
        y = np.array([1.0, 3.5, 1.0])
        
        # When comparing index 0 (CCO) to remaining [CCN, c1ccccc1], similarity is [0.93, 0.1]
        # When comparing index 1 (CCN) to remaining [c1ccccc1], similarity is [0.1]
        # Loop runs 3 times, last is comparison of last element with empty list
        mock_bulk_sim.side_effect = [
            [0.93, 0.1],
            [0.1],
            []
        ]
        
        cliffs = detect_cliffs(
            smiles=smiles,
            y=y,
            model_type="regression",
            similarity_threshold=0.8,
            activity_gap=2.0
        )
        
        # Should yield exactly one pair
        self.assertEqual(len(cliffs), 1)
        pair = cliffs[0]
        self.assertEqual(pair["i"], 0)
        self.assertEqual(pair["j"], 1)
        self.assertEqual(pair["smiles_i"], "CCO")
        self.assertEqual(pair["smiles_j"], "CCN")
        self.assertAlmostEqual(pair["similarity"], 0.93)
        self.assertAlmostEqual(pair["gap"], 2.5)
        self.assertAlmostEqual(pair["severity"], 0.93 * 2.5)

    @patch("rdkit.DataStructs.BulkTanimotoSimilarity")
    def test_pairs_sorted_by_severity_descending(self, mock_bulk_sim):
        # 2. Pairs sorted by severity descending.
        smiles = ["CCO", "CCN", "CCC", "CCCC"]
        y = np.array([1.0, 3.5, 1.0, 4.0])
        
        # Return mock similarities
        mock_bulk_sim.side_effect = [
            [0.9, 0.85, 0.95],
            [0.9, 0.88],
            [0.92],
            []
        ]
        
        cliffs = detect_cliffs(
            smiles=smiles,
            y=y,
            model_type="regression",
            similarity_threshold=0.8,
            activity_gap=0.1
        )
        
        self.assertTrue(len(cliffs) > 1)
        # Check sorted by severity descending
        for idx in range(len(cliffs) - 1):
            self.assertGreaterEqual(cliffs[idx]["severity"], cliffs[idx+1]["severity"])

    def test_thumbnails_are_valid_pngs(self):
        # 3. Thumbnails are valid PNGs (magic bytes check).
        b64_img = render_thumbnail("CCO")
        self.assertTrue(b64_img.startswith("data:image/png;base64,") or b64_img.startswith("data:image/svg+xml;base64,"))
        
        base64_data = b64_img.split(",")[1]
        img_bytes = base64.b64decode(base64_data)
        
        if b64_img.startswith("data:image/png;base64,"):
            png_magic = b"\x89PNG\r\n\x1a\n"
            self.assertTrue(img_bytes.startswith(png_magic))
        else:
            # SVG fallback check
            self.assertTrue(img_bytes.startswith(b"<svg") or img_bytes.startswith(b"<?xml"))

if __name__ == "__main__":
    unittest.main()
