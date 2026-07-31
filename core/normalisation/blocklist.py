from typing import Dict, Any

# Static blocklist — applied ONLY to semantic identity, not to full canonical diff view.
BLOCKLIST = {
    "id", "uuid", "guid",
    "timestamp", "created_at", "updated_at",
    "latency", "latency_ms", "duration",
    "status", "status_code",
    "version", "model_version",
    "request_id", "trace_id",
    "sut_id",
}

def remove_blocklisted_fields(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in obj.items() if k not in BLOCKLIST}
