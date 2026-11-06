"""IP-based rate limiting (slowapi), keyed per IPv4 address or IPv6 /64."""
import ipaddress

from fastapi import Request
from slowapi import Limiter


def _bucket(ip: str) -> str:
    """Collapse an IPv6 address to its /64.

    A residential IPv6 allocation is a /64, and privacy extensions (RFC 4941)
    let the host mint a fresh address from it per connection — so keying on the
    full address would make the IP cap free to bypass. /64 is the smallest unit
    that maps to one subscriber line. IPv4 is returned unchanged.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip  # hostname or malformed — leave as-is
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False).network_address)
    return ip


def client_ip(request: Request) -> str:
    """Real client IP, spoof-resistant.

    The rightmost X-Forwarded-For entry is the one appended by our own reverse
    proxy; anything left of it arrived from the client and can be forged.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[-1].strip() if forwarded else request.client.host


def get_client_ip(request: Request) -> str:
    """The client IP bucketed for rate limiting."""
    return _bucket(client_ip(request))


limiter = Limiter(key_func=get_client_ip)
