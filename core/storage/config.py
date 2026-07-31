from __future__ import annotations
import hashlib
from datetime import datetime

class Config:
    """
    Core Configuration & Cryptographic Utilities.
    """
    @staticmethod
    def make_id(input_str: str) -> str:
        """Generates a stable 12-character ID hash for tracking input payloads."""
        return hashlib.sha1(input_str.encode()).hexdigest()[:12]

    @staticmethod
    def now() -> str:
        """Generates an ISO format UTC timestamp string."""
        return datetime.utcnow().isoformat()

    GOLDEN_BULK_PROMOTION_HARD_LIMIT: int = 200
    BEHAVIOURAL_CONFIG_FILE: str = "tests/behavioural_config.json"