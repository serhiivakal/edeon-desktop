import logging
from typing import List, Optional
from ..schema import JobHistoryEntry

logger = logging.getLogger("edeon_docking")

class JobHistoryService:
    """
    Exposes JobHistory schema structures.
    The primary database CRUD operations are handled directly on the Rust / Tauri side
    to leverage the centralized SQLite connection and migration tree.
    """
    pass
