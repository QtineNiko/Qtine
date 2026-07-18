import ipaddress
import socket
import urllib.request
from urllib.parse import urlparse


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) URLs are allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = socket.getaddrinfo(
        parsed.hostname, port, type=socket.SOCK_STREAM
    )
    if not addresses:
        raise ValueError("URL host could not be resolved")
    for item in addresses:
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError("Private and local network URLs are not allowed")
    return url


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_urlopen(request_or_url, timeout: float = 10):
    url = getattr(request_or_url, "full_url", request_or_url)
    validate_public_http_url(str(url))
    opener = urllib.request.build_opener(_SafeRedirectHandler())
    return opener.open(request_or_url, timeout=timeout)
