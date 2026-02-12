"""Soil DT50 endpoint data pipeline (EAWAG-SOIL / enviPath)."""

from edeon_data.endpoints.dt50.acquire import run_acquire
from edeon_data.endpoints.dt50.curate import run_curate
from edeon_data.endpoints.dt50.split import run_split
from edeon_data.endpoints.dt50.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Soil DT50 dataset."""
    print("=== Starting pipeline run_all for 'dt50' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'dt50' ===\n")
