"""Honey bee endpoints data pipeline (oral and contact)."""

from edeon_data.endpoints.bee.acquire import run_acquire
from edeon_data.endpoints.bee.curate import run_curate
from edeon_data.endpoints.bee.split import run_split
from edeon_data.endpoints.bee.card import run_card

def run_all(endpoint: str) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for honey bee datasets."""
    print(f"=== Starting pipeline run_all for '{endpoint}' ===")
    run_acquire(endpoint=endpoint)
    run_curate(endpoint=endpoint)
    run_split(endpoint=endpoint)
    run_card(endpoint=endpoint)
    print(f"=== Completed pipeline run_all successfully for '{endpoint}' ===\n")
