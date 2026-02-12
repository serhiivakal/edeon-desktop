"""Rat acute oral LD50 endpoint data pipeline (CATMoS NICEATM ICE)."""

from edeon_data.endpoints.rat_ld50.acquire import run_acquire
from edeon_data.endpoints.rat_ld50.curate import run_curate
from edeon_data.endpoints.rat_ld50.split import run_split
from edeon_data.endpoints.rat_ld50.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for rat LD50 dataset."""
    print("=== Starting pipeline run_all for 'rat_acute_oral_ld50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'rat_acute_oral_ld50' ===\n")
