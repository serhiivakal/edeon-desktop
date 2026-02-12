import os
import sys
import pytest
from pathlib import Path

def test_demos_e2e_generation():
    # Add project root to path to resolve scripts module
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # 1. Run the demo orchestrator script
    from scripts.generate_reference_demos import main as run_orchestrator
    
    # Execute the orchestrator
    run_orchestrator()
    
    # 2. Paths check
    root_dir = Path(__file__).parent.parent.parent
    demos_dir = root_dir / "data" / "demos"
    
    assert demos_dir.exists(), "Expected data/demos/ directory to exist!"
    
    # List of 5 expected compounds
    compounds = ["imidacloprid", "glyphosate", "azoxystrobin", "mesotrione", "chlorantraniliprole"]
    
    # Expected files in each compound folder
    expected_files = [
        "predictions.html",
        "predictions.pdf",
        "honeycomb.png",
        "fate_gauge.png",
        "toxicity_panel.png",
        "W1_registration.pdf",
        "W3_tp_sweep.pdf",
        "summary.md"
    ]
    
    for comp_id in compounds:
        comp_path = demos_dir / comp_id
        assert comp_path.exists() and comp_path.is_dir(), f"Expected directory data/demos/{comp_id} to exist!"
        
        for fname in expected_files:
            file_path = comp_path / fname
            assert file_path.exists(), f"Expected file {fname} to be generated in data/demos/{comp_id}!"
            assert file_path.stat().st_size > 0, f"Expected file {fname} in data/demos/{comp_id} to be non-empty!"
            
    print("E2E Demo Orchestration Integration Verification Passed!")
