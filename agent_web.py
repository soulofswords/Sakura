"""Read-only web lookup for the agent. Approved writes are unaffected."""
import html
import ipaddress
import re
import socket
import time
from contextlib import contextmanager
from urllib.parse import parse_qs, urljoin, urlparse

import requests


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Sakura-Agent/1.0'
SEARCH_ENDPOINT = 'https://lite.duckduckgo.com/lite/'
GEMINI_ROOT = 'https://generativelanguage.googleapis.com/v1beta/models'
BRAVE_ENDPOINT = 'https://api.search.brave.com/res/v1/web/search'
WIKI_ENDPOINT = 'https://en.wikipedia.org/w/api.php'
MAX_URL = 2000
MAX_BODY = 600_000
READ_SECONDS = 20
RESULT_LINK = re.compile(r"<a[^>]*href=\"(?P<url>[^\"]+)\"[^>]*>(?P<title>.*?)</a>", re.I | re.S)
SNIPPET = re.compile(r"<td[^>]*class=['\"]result-snippet['\"][^>]*>(?P<text>.*?)</td>", re.I | re.S)
TAGS = re.compile(r'<[^>]+>')
SKIP_TAGS = re.compile(r'<(script|style|noscript|svg)[^>]*>.*?</\1>', re.I | re.S)
META_CHARSET = re.compile(rb'<meta[^>]+charset=["\']?\s*([A-Za-z0-9_.:-]+)', re.I)
WIKI_ARTICLE = re.compile(r'^https://en\.wikipedia\.org/\?curid=(\d+)$')
TEXT_TYPES = ('text/html', 'application/xhtml+xml', 'text/plain', 'text/markdown',
              'application/json', 'application/xml', 'text/xml')


def _clean(fragment, limit=400):
    text = html.unescape(TAGS.sub(' ', fragment or ''))
    # Inline markup becomes a space, which would otherwise leave "word ." in snippets.
    text = re.sub(r'\s+([.,;:!?)\]}])', r'\1', text)
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def _unwrap(location):
    # DuckDuckGo wraps results in a redirect that must be decoded before use.
    target = parse_qs(urlparse(location).query).get('uddg', [''])[0]
    return target or location


def _resolve(host):
    if host in ('localhost', 'metadata.google.internal'):
        raise ValueError('Local network addresses cannot be fetched by the agent.')
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError('That hostname could not be resolved. Check the URL.') from None
    return [ipaddress.ip_address(item[4][0]) for item in infos]


def _vetted(location):
    """Return the host of a URL that is safe to connect to."""
    parts = urlparse(location)
    if parts.scheme not in ('http', 'https'):
        raise ValueError('Only http and https URLs can be fetched.')
    if parts.username or parts.password:
        raise ValueError('Credentials embedded in a URL are not allowed.')
    host = (parts.hostname or '').strip('.').casefold()
    if not host:
        raise ValueError('That URL has no hostname.')
    addresses = _resolve(host)
    # Sakura serves its approval API on loopback; a model-chosen URL must never
    # reach it, nor any other host on this network.
    if not addresses or not all(item.is_global for item in addresses):
        raise ValueError('That address is private, loopback or local-network. The agent fetches public URLs only.')
    return host


def _is_public(text):
    try:
        return ipaddress.ip_address(text).is_global
    except ValueError:
        return False


@contextmanager
def _pinned(host):
    """Every later lookup for this host is filtered to public answers, otherwise a
    second resolution during connect can return a private address (DNS rebinding).
    Answers are filtered, never replayed, so the connect port and family stay intact."""
    original = socket.getaddrinfo

    def pinned(name, *args, **kwargs):
        infos = original(name, *args, **kwargs)
        if str(name).strip('.').casefold() != host:
            return infos
        kept = [item for item in infos if _is_public(item[4][0])]
        if not kept:
            raise socket.gaierror(f'{host} resolves only to addresses the agent may not reach.')
        return kept

    socket.getaddrinfo = pinned
    try:
        yield
    finally:
        socket.getaddrinfo = original


def _body(response, deadline):
    chunks = []
    size = 0
    for chunk in response.raw.stream(65536, decode_content=True):
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_BODY:
            break
        if time.monotonic() > deadline:
            raise ValueError('That page took too long to send its content. Try a different source.')
    return b''.join(chunks)[:MAX_BODY]


def _decode(body, content_type):
    candidates = []
    declared = re.search(r'charset=["\']?\s*([A-Za-z0-9_.:-]+)', content_type, re.I)
    if declared:
        candidates.append(declared.group(1))
    inline = META_CHARSET.search(body[:4096])
    if inline:
        candidates.append(inline.group(1).decode('ascii', 'ignore'))
    candidates.append('utf-8')
    for name in candidates:
        try:
            return body.decode(name, errors='replace')
        except LookupError:
            continue
    return body.decode('utf-8', errors='replace')


def _support_snippet(supports, index):
    for item in supports:
        if index in (item.get('groundingChunkIndices') or []):
            text = (item.get('segment') or {}).get('text', '')
            if isinstance(text, str) and text.strip():
                return _clean(text, 300)
    return ''


def _brave(query, limit, key):
    """Brave Search API. Index results only; the description is already their snippet."""
    response = requests.get(BRAVE_ENDPOINT, params={'q': query, 'count': limit, 'country': 'us', 'search_lang': 'en'},
                            headers={'X-Subscription-Token': key, 'Accept': 'application/json'},
                            timeout=(5, READ_SECONDS))
    response.raise_for_status()
    hits = (response.json().get('web') or {}).get('results') or []
    results = []
    for hit in hits[:limit]:
        url, title = hit.get('url', ''), hit.get('title', '')
        if not isinstance(url, str) or not url.startswith('http') or len(url) > MAX_URL:
            continue
        if not isinstance(title, str) or not title:
            continue
        try:
            _vetted(url)
        except ValueError:
            continue
        description = hit.get('description', '')
        results.append({'title': _clean(title, 200), 'url': url,
                        'snippet': _clean(description if isinstance(description, str) else '')})
    if not results:
        raise ValueError('no usable results')
    return results


def _grounded(query, limit, key, gemini_model):
    """Google Search grounding through the Gemini key the user already has configured.
    Sources come from the API's own grounding metadata, so nothing is scraped."""
    body = {'contents': [{'role': 'user', 'parts': [{'text':
        f'Search the public web for: {query}\n'
        f'Return up to {limit} distinct sources. For each source give its title, its URL and one '
        'sentence taken from that source. No commentary and no sources beyond those you searched.'}]}],
        'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 1200},
        'tools': [{'google_search': {}}]}
    response = requests.post(f'{GEMINI_ROOT}/{gemini_model}:generateContent',
                             headers={'x-goog-api-key': key}, json=body,
                             timeout=(5, READ_SECONDS + 25))
    response.raise_for_status()
    candidate = (response.json().get('candidates') or [{}])[0]
    metadata = candidate.get('groundingMetadata') or {}
    chunks = metadata.get('groundingChunks') or []
    results = []
    for index, chunk in enumerate(chunks):
        web = chunk.get('web') or {}
        url, title = web.get('uri', ''), web.get('title', '')
        if not isinstance(url, str) or not url.startswith('http') or len(url) > MAX_URL:
            continue
        if not isinstance(title, str) or not title:
            continue
        try:
            _vetted(url)
        except ValueError:
            continue
        results.append({'title': _clean(title, 200), 'url': url,
                        'snippet': _support_snippet(metadata.get('groundingSupports') or [], index)})
        if len(results) >= limit:
            break
    if not results:
        raise ValueError('no sources in the grounded answer')
    return results


def _duckduckgo(query, limit):
    response = requests.post(SEARCH_ENDPOINT, data={'q': query, 'kl': 'us-en'},
                             headers={'User-Agent': USER_AGENT}, timeout=(5, READ_SECONDS),
                             allow_redirects=False)
    page = response.text or ''
    links = [(item.start(), item.end(), item.group('url'), _clean(item.group('title'), 200))
             for item in RESULT_LINK.finditer(page) if item.group('url').startswith('http')]
    if response.status_code != 200 or not links:
        if re.search(r'no (?:more )?results', page, re.I):
            return []
        # A bot-challenge page (DuckDuckGo answers HTTP 202 with a CAPTCHA) is not an
        # empty result set; reporting it lets search() try another provider.
        raise ValueError(f'HTTP {response.status_code} challenge page')
    snippets = [(item.start(), _clean(item.group('text'))) for item in SNIPPET.finditer(page)]
    results = []
    for index, (start, end, raw, title) in enumerate(links):
        nxt = links[index + 1][0] if index + 1 < len(links) else len(page)
        snippet = next((text for position, text in snippets if end < position < nxt), '')
        url = html.unescape(_unwrap(raw))
        if len(url) > MAX_URL or not title or 'duckduckgo.com' in urlparse(url).netloc:
            continue
        try:
            _vetted(url)
        except ValueError:
            continue
        results.append({'title': title, 'url': url, 'snippet': snippet})
        if len(results) >= limit:
            break
    return results


def _wikipedia(query, limit):
    response = requests.get('https://en.wikipedia.org/w/api.php',
                            params={'action': 'query', 'list': 'search', 'srsearch': query,
                                    'srlimit': limit, 'srprop': 'snippet', 'format': 'json'},
                            headers={'User-Agent': USER_AGENT}, timeout=(5, READ_SECONDS))
    response.raise_for_status()
    hits = response.json().get('query', {}).get('search', [])
    results = []
    for hit in hits[:limit]:
        title, snippet, identifier = hit.get('title', ''), hit.get('snippet', ''), hit.get('pageid')
        if not isinstance(title, str) or not isinstance(identifier, int) or identifier <= 0:
            continue
        results.append({'title': _clean(title, 200), 'url': f'https://en.wikipedia.org/?curid={identifier}',
                        'snippet': _clean(snippet if isinstance(snippet, str) else '', 400)})
    return results


def search(query, max_results=6, credentials=None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('Enter a search query.')
    if len(query) > 300:
        raise ValueError('Search queries are limited to 300 characters.')
    try:
        limit = int(max_results)
    except (TypeError, ValueError):
        raise ValueError('Result count must be a number.') from None
    limit = min(8, max(1, limit))
    term = query.strip()
    key = gemini_model = brave_key = ''
    if credentials:
        values = [str(item or '') for item in tuple(credentials)] + ['', '', '']
        key, gemini_model, brave_key = values[:3]
    sources = []
    if brave_key:
        sources.append(('Brave Search', lambda: _brave(term, limit, brave_key)))
    if key and gemini_model:
        sources.append(('Google Search via Gemini',
                        lambda: _grounded(term, limit, key, gemini_model)))
    sources += [('DuckDuckGo', lambda: _duckduckgo(term, limit)),
                ('Wikipedia', lambda: _wikipedia(term, limit))]
    failures = []
    for name, gather in sources:
        try:
            results = gather()
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as error:
            failures.append(f'{name} ({str(error)[:70]})')
            continue
        if results:
            return {'ok': True, 'results': results, 'provider': name}
    if len(failures) == len(sources):
        raise ValueError('Web search is unavailable: ' + '; '.join(failures) +
                         '. Try web.fetch on a URL you already know.')
    return {'ok': True, 'results': [], 'note': 'No public, readable results were found for that query.'}


def fetch(url, characters=12000):
    if not isinstance(url, str) or len(url.strip()) > MAX_URL:
        raise ValueError(f'Provide one URL up to {MAX_URL} characters.')
    try:
        cap = int(characters)
    except (TypeError, ValueError):
        raise ValueError('Character limit must be a number.') from None
    cap = min(20000, max(500, cap))
    location = url.strip()
    visits = []
    response = None
    try:
        for _ in range(4):
            host = _vetted(location)
            with _pinned(host):
                response = requests.get(location, headers={'User-Agent': USER_AGENT},
                                        timeout=(5, READ_SECONDS), allow_redirects=False, stream=True)
            visits.append(location)
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            target = response.headers.get('location', '')
            if not target:
                raise ValueError('That redirect announced no destination URL.')
            location = urljoin(location, target)
            response.close()
        else:
            raise ValueError('That URL redirects too many times to be read.')
        if response.status_code >= 400:
            raise ValueError(f'That page returned HTTP {response.status_code}.')
        content_type = response.headers.get('content-type', '')
        kind = content_type.split(';')[0].casefold()
        if kind not in TEXT_TYPES:
            raise ValueError(f'Only web pages and text can be read. That URL returned {kind or "an unknown type"}.')
        body = _body(response, time.monotonic() + READ_SECONDS)
    finally:
        if response is not None:
            response.close()
    text = _decode(body, content_type)
    if 'html' in kind or 'xml' in kind:
        text = SKIP_TAGS.sub(' ', text)
    text = _clean(text, 200_000)
    if not text:
        raise ValueError('That page had no readable text. It may require JavaScript; try a different source.')
    return {'ok': True, 'url': visits[-1], 'content_type': kind,
            'text': text[:cap], 'truncated': len(text) > cap, 'source': 'fetched directly'}


def _wiki_extract(identifier, characters):
    """The plain lead paragraph, not the article HTML with its navigation chrome."""
    response = requests.get(WIKI_ENDPOINT, params={'action': 'query', 'prop': 'extracts', 'explaintext': 1,
                                                   'exintro': 1, 'pageids': identifier, 'format': 'json'},
                            headers={'User-Agent': USER_AGENT}, timeout=(5, READ_SECONDS))
    response.raise_for_status()
    for page in (response.json().get('query', {}).get('pages') or {}).values():
        text = page.get('extract', '')
        if isinstance(text, str) and text.strip():
            return {'title': str(page.get('title', '')) or 'Wikipedia article',
                    'text': re.sub(r'\s+', ' ', text).strip()[:characters]}
    return None


def lookup(query, credentials=None, characters=3500):
    """One round trip for the companion: search, then read the best usable result."""
    found = search(query, 3, credentials)
    for item in found.get('results', []):
        article = WIKI_ARTICLE.match(item['url'])
        try:
            if article:
                page = _wiki_extract(article.group(1), characters)
            else:
                read = fetch(item['url'], characters)
                page = {'title': item['title'], 'url': read['url'], 'text': read['text']}
        except (requests.RequestException, ValueError):
            continue
        if page and len(page['text']) >= 120:
            return {'title': page['title'], 'url': item['url'], 'snippet': item['snippet'],
                    'text': page['text'], 'provider': found.get('provider', '')}
    return None
