"""Bird acute oral LD50 endpoint data pipeline (ECOTOX + EFSA OpenFoodTox)."""

from edeon_data.endpoints.bird.acquire import run_acquire
from edeon_data.endpoints.bird.curate import run_curate
from edeon_data.endpoints.bird.split import run_split
from edeon_data.endpoints.bird.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Bird Acute Oral LD50 dataset."""
    print("=== Starting pipeline run_all for 'bird_acute_oral_ld50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'bird_acute_oral_ld50' ===\n")
