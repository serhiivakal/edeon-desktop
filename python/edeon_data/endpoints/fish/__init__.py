"""Fish acute LC50 endpoint data pipeline (ECOTOX + Williams)."""

from edeon_data.endpoints.fish.acquire import run_acquire
from edeon_data.endpoints.fish.curate import run_curate
from edeon_data.endpoints.fish.split import run_split
from edeon_data.endpoints.fish.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for fish LC50 dataset."""
    print("=== Starting pipeline run_all for 'fish_acute_lc50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'fish_acute_lc50' ===\n")
