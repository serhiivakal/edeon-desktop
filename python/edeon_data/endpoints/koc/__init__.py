"""Soil Koc endpoint data pipeline (OPERA)."""

from edeon_data.endpoints.koc.acquire import run_acquire
from edeon_data.endpoints.koc.curate import run_curate
from edeon_data.endpoints.koc.split import run_split
from edeon_data.endpoints.koc.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Soil Koc dataset."""
    print("=== Starting pipeline run_all for 'soil_koc' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'soil_koc' ===\n")
