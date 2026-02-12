import os
import unittest
import tempfile
import shutil
import asyncio
from pathlib import Path
from datetime import datetime

from rdkit import Chem
from edeon_docking.schema import PreparedReceptor, ReceptorPreparationParams, DockingJobResult, DockedPose
from edeon_generation.crem_engine import CReMGenerationEngine
from edeon_generation.easydock_wrapper import EasyDockService
from edeon_generation.crem_dock import CReMDockPipeline
from edeon_docking.services.receptor_service import ReceptorService
from edeon_docking.services.docking_service import DockingService

class TestGenerationAndDocking(unittest.TestCase):

    def setUp(self):
        # Create a temp directory for the test database
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_crem.db"
        
        # We will also create dummy files for pdbqt since the docking service checks if files exist
        self.rec_pdbqt = Path(self.test_dir) / "rec.pdbqt"
        with open(self.rec_pdbqt, "w") as f:
            f.write("DUMMY RECEPTOR PDBQT")
            
        # Initialize engine with the custom database path
        self.engine = CReMGenerationEngine(fragments_db_path=self.db_path)

        # Construct mock receptor
        self.receptor = PreparedReceptor(
            receptor_hash="mock_receptor_hash",
            pdb_source="mock_source",
            pdbqt_path=str(self.rec_pdbqt),
            raw_pdb_path=str(self.rec_pdbqt),  # dummy
            preparation_params=ReceptorPreparationParams(),
            metadata={},
            het_entries=[],
            cocrystal_ligands=[],
            prepared_at="2026-06-21T00:00:00"
        )

        # Mock the get_cached method at the class level so all instances of ReceptorService resolve it
        self._orig_get_cached = ReceptorService.get_cached
        ReceptorService.get_cached = lambda s, h: self.receptor if h == "mock_receptor_hash" else None

        # Mock DockingService.run to return a simulated docking result
        async def mock_run(s, spec, cancel_event=None):
            poses = [
                DockedPose(
                    pose_index=1,
                    score_kcal_per_mol=-8.5,
                    rmsd_to_top=0.0,
                    rmsd_to_prev=0.0,
                    pdbqt_block="MODEL 1\nREMARK VINA RESULT: -8.5  0.000  0.000\nENDMDL\n",
                    sdf_block="MOCK SDF BLOCK"
                )
            ]
            return DockingJobResult(
                job_id="mock_job_id",
                spec=spec,
                poses=poses,
                elapsed_seconds=0.1,
                engine_version="AutoDock Vina (simulated)",
                command_line="vina mock",
                warnings=[],
                completed_at=datetime.utcnow().isoformat()
            )
            
        self._orig_run = DockingService.run
        DockingService.run = mock_run

    def tearDown(self):
        # Restore original methods
        ReceptorService.get_cached = self._orig_get_cached
        DockingService.run = self._orig_run
        # Cleanup
        shutil.rmtree(self.test_dir)

    def test_crem_database_bootstrapping(self):
        """Verify that the engine bootstraps a valid database if missing."""
        self.assertTrue(self.db_path.exists())
        # The database should be a non-empty sqlite file
        self.assertGreater(self.db_path.stat().st_size, 0)

    def test_crem_mutation_generation(self):
        """Verify CReM mutator core generates expected mutants for a seed smiles."""
        # Using a smiles from the bootstrap list
        parent_smiles = "Cc1ccccc1" 
        mutants = self.engine.generate_mutants(
            parent_smiles=parent_smiles,
            radius=1,
            min_size=1,
            max_size=3,
            max_mutants=10
        )
        
        self.assertIsInstance(mutants, list)
        # Even with a tiny database, at least one mutant should be generated
        self.assertGreater(len(mutants), 0)
        
        # Verify result fields
        first_mutant = mutants[0]
        self.assertEqual(first_mutant.parent_smiles, parent_smiles)
        self.assertTrue(Chem.MolFromSmiles(first_mutant.mutant_smiles) is not None)
        self.assertIsInstance(first_mutant.similarity_to_parent, float)
        self.assertGreaterEqual(first_mutant.similarity_to_parent, 0.0)
        self.assertLessEqual(first_mutant.similarity_to_parent, 1.0)
        
        # Verify they are sorted by similarity descending
        similarities = [m.similarity_to_parent for m in mutants]
        self.assertEqual(similarities, sorted(similarities, reverse=True))

    def test_easydock_batch_docking(self):
        """Verify EasyDock batch virtual screening wrapper."""
        # Initialize easy dock service
        dock_service = EasyDockService()
        
        # Let's dock a couple of simple SMILES
        smiles_batch = ["c1ccccc1", "Cc1ccccc1"]
        
        # Run async batch docking synchronously using asyncio
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(
            dock_service.dock_batch(
                receptor=self.receptor,
                ligand_smiles=smiles_batch,
                box_center=(0.0, 0.0, 0.0),
                box_size=(20.0, 20.0, 20.0),
                engine="vina"
            )
        )
        
        self.assertEqual(len(results), len(smiles_batch))
        for res in results:
            self.assertIn(res.smiles, smiles_batch)
            self.assertIsInstance(res.docking_score, float)
            self.assertLess(res.docking_score, 0.0)
            self.assertIsInstance(res.poses, list)
            self.assertGreater(len(res.poses), 0)
            self.assertIsNone(res.error)

    def test_cremdock_closed_loop_pipeline(self):
        """Verify that the closed loop de novo design pipeline runs end-to-end."""
        pipeline = CReMDockPipeline(fragments_db_path=self.db_path)
        
        # Run pipeline
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(
            pipeline.run(
                parent_smiles="Cc1ccccc1",
                receptor=self.receptor,
                box_center=(0.0, 0.0, 0.0),
                box_size=(20.0, 20.0, 20.0),
                n_iterations=2,
                population_size=5,
                keep_top_n=2,
                weights={
                    "pesticide_likeness": 1.0,
                    "selectivity": 1.0,
                    "resistance": 1.0,
                    "toxicity": 1.0,
                    "environmental_safety": 1.0
                }
            )
        )
        
        self.assertEqual(result.parent_smiles, "Cc1ccccc1")
        self.assertEqual(result.receptor_id, "mock_receptor_hash")
        self.assertGreater(len(result.best_compounds), 0)
        self.assertEqual(len(result.iterations), 2)
        self.assertGreater(result.total_compounds_generated, 0)
        self.assertGreater(result.total_compounds_docked, 0)
        
        # Check composite score is correctly computed
        best_comp = result.best_compounds[0]
        # composite_score = mpo_score - 1.2 * docking_score
        expected_composite = round(best_comp.mpo_score - 1.2 * best_comp.docking_score, 2)
        self.assertEqual(best_comp.composite_score, expected_composite)

if __name__ == "__main__":
    unittest.main()
