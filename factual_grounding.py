"""Bounded fact checks and conservative guards; no model-generated URLs or actions."""
import re
import time
from html.parser import HTMLParser
from threading import Lock

import requests

RULES = (
    'Prefer uncertainty over fabrication. '
    'Separate verified tool results, user-provided claims, and your own uncertain knowledge. '
    'Never invent an exact specification, number, citation, quote, date or source to fill a gap. '
    'For current prices, releases, specifications and availability, use supplied verified evidence; '
    'otherwise state what you cannot verify. Do not claim a live search or successful action without a tool result. '
    'Earlier assistant statements are not independent evidence. Respect user corrections without blindly endorsing them. '
    'Hardware usage is a momentary load, not a hardware specification or proof of performance. '
    'An opinion about a PC must refer to its supplied components, not your own wellbeing. '
    'When essential facts are missing, ask one specific question instead of guessing.'
)

_cache = {}
_lock = Lock()
_GPU_PAGES = {
    # NVIDIA lists both the original 12 GB and later 8 GB desktop RTX 3060
    # configurations in this family table.
    '3060': 'https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3060-3060ti/',
    '5060': 'https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5060-family/',
    '5060TI': 'https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5060-family/',
    '5090': 'https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/',
    '5080': 'https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5080/',
    '4090': 'https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/',
}


def trusted_gpu_page(url):
    return url in _GPU_PAGES.values() or bool(re.fullmatch(
        r'https://www\.nvidia\.com/en-us/geforce/graphics-cards/\d0-series/rtx-\d{4}(?:-ti|-super)?(?:-family)?/',url))


class _SpecTables(HTMLParser):
    def __init__(self):
        super().__init__();self.tables=[];self.rows=None;self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.rows=[]
        elif tag=='tr' and self.rows is not None:self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(re.sub(r'\s+',' ',' '.join(self.cell)).strip());self.cell=None
        elif tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None
        elif tag=='table' and self.rows is not None:
            self.tables.append(self.rows);self.rows=None


def _model_memory(page,number,suffix=''):
    """Match the exact product column, never the neighbouring Ti memory."""
    parser=_SpecTables();parser.feed(page);values=set()
    target=(number,suffix.upper())
    for table in parser.tables:
        columns=[]
        for row in table:
            for index,cell in enumerate(row):
                cell=cell.replace('G eForce','GeForce')
                match=re.fullmatch(r'(?:NVIDIA\s+)?(?:GeForce\s+)?RTX\s*(\d{4})\s*(Ti|SUPER)?',cell,re.I)
                if match and (match[1],(match[2] or '').upper())==target:columns.append(index)
        for row in table:
            # NVIDIA's family page labels this row "Memory Size" while the
            # comparison/spec pages use "Standard Memory Config".
            if not any(re.fullmatch(r'(?:Standard Memory Config(?:uration)?|Memory Size)',cell,re.I) for cell in row):continue
            for index in columns:
                if index>=len(row):continue
                cell=row[index]
                memory_sizes=re.findall(r'(\d{1,3})\s*GB(?:\s*GDDR\dX?)?',cell,re.I)
                if memory_sizes and re.fullmatch(r'\s*\d{1,3}\s*GB(?:\s*GDDR\dX?)?(?:\s*/\s*\d{1,3}\s*GB(?:\s*GDDR\dX?)?)*\s*',cell,re.I):
                    values.add(tuple(sorted(set(map(int,memory_sizes)))))
    if len(values)==1:return next(iter(values))
    if values:return None
    # Family tables need column matching even if only one value appears nearby.
    if any(any(re.search(r'RTX\s*\d{4}',cell,re.I) for cell in row) for table in parser.tables for row in table):return None
    value=_memory_gb(page)
    return (value,) if value is not None and not suffix else None


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _memory_gb(page):
    parser = _VisibleText()
    parser.feed(page)
    text = re.sub(r'\s+', ' ', ' '.join(parser.parts))
    # Only the labelled specification, never a free-floating number, script,
    # comparison card, or a model-generated summary of the webpage.
    values = set(re.findall(r'Standard Memory Config(?:uration)?\s*[:|]?\s*(\d{1,3})\s*GB\s*GDDR\d', text, re.I))
    return int(next(iter(values))) if len(values) == 1 else None


def _mentioned_models(question):
    """RTX-prefixed models plus bare numbers, so "vram of the 5090" is verified too."""
    models = {(number, (suffix or '').upper())
              for number, suffix in re.findall(r'\bRTX\s*(\d{4})\s*(Ti|SUPER)?\b', question, re.I)}
    # A bare number only counts when this file already has a verified page for it; that
    # keeps 1080p, a year, and another vendor's model name out of the lookup.
    found = []
    for key in _GPU_PAGES:
        pattern = (r'(?<![A-Za-z0-9])' + re.escape(key[:4])
                   + (r'\s*' + re.escape(key[4:]) if len(key) > 4 else '')
                   + r'\b(?!\s*(?:p|gb|mb|tb|hz|fps|inches?|pixels?|[@x]))')
        for hit in re.finditer(pattern, question, re.I):
            found.append((hit.start(), hit.end(), key[:4], key[4:].upper()))
    for start, end, number, suffix in found:
        # "5060 Ti" also contains "5060"; the longer reading is the model actually named.
        if any(other[0] <= start and end <= other[1] and other[1] - other[0] > end - start for other in found):
            continue
        models.add((number, suffix))
    return models


def gpu_memory_lookup(question,allow_discovery=False):
    """Return None for unrelated chat; unavailable facts never fall back to guessing."""
    models = _mentioned_models(question)
    if not models or not re.search(r'\b(?:VRAM|memory|GB|gigabytes?|specs|specifications)\b|\d+\s*GB\b|वीरैम|मेमोरी', question, re.I):
        return None
    if re.search(r'\b(?:like my|my pc|my specs|my computer|my gpu|opinion|good for|enough for)\b', question, re.I):
        return None
    if re.search(r'\b(?:imagine|fiction|pretend|hypothetical|modified|modded|laptop|mobile)\b', question, re.I):
        return None
    if len(models) != 1:
        return 'Please ask about one desktop GPU at a time so I can verify its memory specification.'
    number, suffix = next(iter(models))
    # Expand only after verifying each manufacturer's URL and parser format.
    model_key=number+suffix
    if model_key not in _GPU_PAGES and not allow_discovery:
        return 'I do not have a verified memory specification for that GPU here. Please share its manufacturer specification page; I should not guess the VRAM.'
    urls=[_GPU_PAGES[model_key]] if model_key in _GPU_PAGES else [
        f'https://www.nvidia.com/en-us/geforce/graphics-cards/{number[:2]}-series/rtx-{number}-family/',
        f'https://www.nvidia.com/en-us/geforce/graphics-cards/{number[:2]}-series/rtx-{number}/']
    for url in urls:
        value=_fetch_model_memory(url,number,suffix)
        if value is not None:
            memory=' or '.join(f'{size} GB' for size in value)
            return f'NVIDIA lists the standard desktop GeForce RTX {number}{" "+suffix.title() if suffix else ""} with {memory} of VRAM.\nSource: {url}'
    return f'I could not verify the RTX {number}{" "+suffix if suffix else ""} memory specification from NVIDIA right now. I should not guess the VRAM.'


def _fetch_model_memory(url,number,suffix):
    cache_key=(url,number,suffix)
    with _lock:
        cached = _cache.get(cache_key)
    value = cached[1] if cached and time.monotonic() - cached[0] < 3600 else None
    if value is None:
        try:
            response = requests.get(url, timeout=(2, 4), allow_redirects=False)
            response.raise_for_status()
            if len(response.content) > 3_000_000:
                raise ValueError('Unexpected specification size')
            value = _model_memory(response.text,number,suffix)
            if value is None:
                raise ValueError('No unambiguous labelled memory specification')
            with _lock:
                _cache[cache_key] = (time.monotonic(), value)
        except (requests.RequestException, ValueError):
            return None
    return value


def unsupported_tool_claim(reply, question):
    if re.search(r'\b(?:story|fiction|roleplay|pretend|example|translate|quote)\b', question, re.I):
        return False
    if re.match(r'\s*(?:if|suppose|imagine)\b', reply, re.I):
        return False
    # Generated citations are not retrieved sources. Direct tool responses
    # bypass generation; preserve a user's supplied citation when discussing it.
    citations = re.findall(r'\b(?:source|citation)\s*:\s*(https?://[^\s]+)', reply, re.I)
    if any(url.rstrip('.,)') not in question for url in citations):
        return True
    return bool(re.search(
        r"\bI (?:have |just |already )?(?:searched (?:the (?:web|internet)|online)|"
        r"checked (?:online|the (?:web|internet|official (?:website|specifications)))|"
        r"opened (?:your|the) (?:app|file|browser)|installed|deleted|sent (?:the|your) (?:email|message))\b",
        reply, re.I))
