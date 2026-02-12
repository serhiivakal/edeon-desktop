"""Earthworm acute LC50 endpoint data pipeline (Kotli 2024 / QsarDB)."""

from edeon_data.endpoints.earthworm.acquire import run_acquire
from edeon_data.endpoints.earthworm.curate import run_curate
from edeon_data.endpoints.earthworm.split import run_split
from edeon_data.endpoints.earthworm.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for Earthworm dataset."""
    print("=== Starting pipeline run_all for 'earthworm' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'earthworm' ===\n")
