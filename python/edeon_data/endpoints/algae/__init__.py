"""Algae growth EC50 endpoint data pipeline (ECOTOX)."""

from edeon_data.endpoints.algae.acquire import run_acquire
from edeon_data.endpoints.algae.curate import run_curate
from edeon_data.endpoints.algae.split import run_split
from edeon_data.endpoints.algae.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Algae Growth EC50 dataset."""
    print("=== Starting pipeline run_all for 'algae_growth_ec50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'algae_growth_ec50' ===\n")
