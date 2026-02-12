"""Skin Sensitization endpoint data pipeline (NICEATM LLNA / ICCVAM CCS)."""

from edeon_data.endpoints.skin_sens.acquire import run_acquire
from edeon_data.endpoints.skin_sens.curate import run_curate
from edeon_data.endpoints.skin_sens.split import run_split
from edeon_data.endpoints.skin_sens.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Skin Sensitization dataset."""
    print("=== Starting pipeline run_all for 'skin_sens' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'skin_sens' ===\n")
