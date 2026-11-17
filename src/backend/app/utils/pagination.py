import base64
import json
from typing import Optional, Tuple, Any

def encode_cursor(created_at: Any, item_id: str) -> str:
    """Encodes created_at timestamp and item_id into base64 cursor."""
    iso_time = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
    data = json.dumps({"t": iso_time, "id": item_id})
    return base64.urlsafe_b64encode(data.encode("utf-8")).decode("utf-8")

def decode_cursor(cursor_str: Optional[str]) -> Optional[Tuple[str, str]]:
    """Decodes cursor back into (iso_time, item_id). Returns None if invalid."""
    if not cursor_str:
        return None
    try:
        decoded_bytes = base64.urlsafe_b64decode(cursor_str.encode("utf-8"))
        payload = json.loads(decoded_bytes.decode("utf-8"))
        return payload.get("t"), payload.get("id")
    except Exception:
        return None

