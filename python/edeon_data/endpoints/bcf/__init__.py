"""BCF bioconcentration endpoint data pipeline (OPERA)."""

from edeon_data.endpoints.bcf.acquire import run_acquire
from edeon_data.endpoints.bcf.curate import run_curate
from edeon_data.endpoints.bcf.split import run_split
from edeon_data.endpoints.bcf.card import run_card

def run_all(endpoint: str = None) -> None:
    """Runs the entire end-to-end curation and splitting pipeline for BCF dataset."""
    print("=== Starting pipeline run_all for 'bcf' ===")
    run_acquire()
    run_curate()
    run_split()
    run_card()
    print("=== Completed pipeline run_all successfully for 'bcf' ===\n")
