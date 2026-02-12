"""Daphnia acute EC50 endpoint data pipeline (ECOTOX)."""

from edeon_data.endpoints.daphnia.acquire import run_acquire
from edeon_data.endpoints.daphnia.curate import run_curate
from edeon_data.endpoints.daphnia.split import run_split
from edeon_data.endpoints.daphnia.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Daphnia acute EC50 dataset."""
    print("=== Starting pipeline run_all for 'daphnia_acute_ec50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'daphnia_acute_ec50' ===\n")
