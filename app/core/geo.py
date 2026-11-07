"""Country of an IP address from the local DB-IP Lite country file. The IP is never stored."""
import logging
from functools import lru_cache

from app.core.config import GEO_DB_PATH

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _reader():
    try:
        import maxminddb
        return maxminddb.open_database(GEO_DB_PATH)
    except Exception as e:  # missing file (tests, a dev build without it): no country, not an error
        log.warning("[geo] no country database at %s: %s", GEO_DB_PATH, e)
        return None


def country(ip: str | None) -> str | None:
    """Two-letter ISO code, or None when unknown (private address, no database)."""
    reader = _reader()
    if not ip or reader is None:
        return None
    try:
        rec = reader.get(ip)
    except ValueError:
        return None
    code = ((rec or {}).get("country") or {}).get("iso_code")
    return code if isinstance(code, str) and len(code) == 2 else None
