"""Per-process capability for the authenticated phone relay's internal PC calls."""
import secrets
INTERNAL_TOKEN=secrets.token_urlsafe(32)
def internal_headers():return {'X-Sakura-Internal':INTERNAL_TOKEN}
def is_internal(request):
    host=request.client.host if request.client else ''
    return host in ('127.0.0.1','::1') and secrets.compare_digest(request.headers.get('x-sakura-internal',''),INTERNAL_TOKEN)
