"""Fresh, source-labelled weather forecasts and news headlines on request."""
import re
from datetime import datetime, timezone, date, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree
import requests


def lookup_with_context(text, pending=None, news_area=''):
    """Carry only an immediately pending weather-location question forward."""
    if pending is not None and not re.search(r'\b(weather|forecast|temperature|news|headlines|open|launch|search|hello|hi|hey|thanks|cancel)\b', text, re.I):
        if re.fullmatch(r"[\w\s,.'-]{1,100}", text.strip(), re.UNICODE):
            text = f"weather in {text.strip()} {pending}"
    reply = lookup(text, news_area=news_area)
    if reply == 'Which city would you like the weather forecast for?':
        _, when = _weather_date(text)
        return reply, ('on ' + when.isoformat()) if when else ''
    return reply, None


def _weather_date(text):
    today = datetime.now().date()
    match = re.search(r'\b\d{4}-\d{2}-\d{2}\b', text)
    if match:
        return text[:match.start()] + text[match.end():], date.fromisoformat(match.group())
    months = 'january february march april may june july august september october november december'.split()
    match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(months) + r')(?:\s+(\d{4}))?\b', text, re.I)
    if match:
        when = date(int(match.group(3) or today.year), months.index(match.group(2).lower())+1, int(match.group(1)))
        return text[:match.start()] + text[match.end():], when
    match = re.search(r'\b(today|tomorrow)\b', text, re.I)
    if match:
        return text[:match.start()] + text[match.end():], today + timedelta(days=match.group().lower()=='tomorrow')
    return text, None


def _city(text):
    # Restrict prepositions to the weather phrase: "for me ... weather in Mumbai"
    # must never geocode "me ... weather in Mumbai".
    weather = re.search(r"\b(?:weather|forecast|temperature)\b(.*)", text, re.I)
    tail=weather.group(1).strip() if weather else ''
    match=re.match(r"(?:(?:right now|currently|now)\s+)?(?:in|for|at|of)\s+(.+)",tail,re.I)
    city=match.group(1) if match else tail
    city=city.strip(' ?.,!')
    city=re.sub(r"(?:\s+(?:right now|now|currently|today|tomorrow|please|this week|this morning|this evening|on))+$",'',city,flags=re.I).strip(' ?.,!')
    if re.fullmatch(r"(?:is|like|here|there|on|the|right now|now|currently|today|tomorrow|in|for|of|at)?",city,re.I):return ''
    return city[:100]


def news_query(text, area=''):
    text = text.lower().replace('’', "'").strip(' ?.!')
    text = re.sub(r'^(?:(?:can|could|would|will) you (?:please )?|please )', '', text)
    text = re.sub(r'^(?:(?:tell|show|give) me |get |read )', '', text)
    explicit = re.search(r'\b(?:news|headlines)\s+(?:about|on|in|for|of|from)\s+(.+)', text)
    if explicit:
        query = explicit.group(1).strip(' ?.!')
    else:
        query = re.sub(r'\b(?:the|latest|current|today|today\x27s|any|some|news|headlines|please|now)\b', '', text).strip()
    if re.fullmatch(r'(?:local|my city|my state|near me|around me|here|in my area|for my area|my area)', query):
        return (str(area).strip()[:100] + ' India') if str(area).strip() else None
    if not query and str(area).strip():return str(area).strip()[:100] + ' India'
    return query[:180]


def lookup(text, news_area=''):
    if re.search(r'\b(?:on (?:my |the |this |your )?screen|in (?:this|the) (?:image|picture|video))\b',text,re.I):return None
    if re.search(r'\b(weather|forecast|temperature)\b', text, re.I):
        try:
            location_text, when = _weather_date(text)
        except ValueError:
            return 'That date is invalid. Please use a date such as 20 October 2026.'
        city=_city(location_text)
        if not city:
            return 'Which city would you like the weather forecast for?'
        if when and not 0 <= (when-datetime.now().date()).days <= 15:
            return f'{when.isoformat()} is outside this live forecast service\'s next 16 days. I cannot provide a reliable forecast for that date yet.'
        try:
            response = requests.get('https://geocoding-api.open-meteo.com/v1/search',
                                    params={'name':city,'count':1,'language':'en'}, timeout=(3,5))
            response.raise_for_status()
            places = response.json().get('results', [])
            if not places:
                return f'I could not find the city {city}. Please include the country.'
            place = places[0]
            params = {
                'latitude':place['latitude'],'longitude':place['longitude'],'timezone':'auto',
                'current':'temperature_2m', 'daily':'temperature_2m_max,temperature_2m_min,precipitation_probability_max',
                'forecast_days':3}
            if when:
                params.update(start_date=when.isoformat(), end_date=when.isoformat())
                params.pop('forecast_days')
                params.pop('current')
            current_only=not when and bool(re.search(r'\b(?:current|now|temperature)\b',text,re.I))
            if current_only:params.pop('daily');params.pop('forecast_days')
            response = requests.get('https://api.open-meteo.com/v1/forecast', params=params, timeout=(3,5))
            response.raise_for_status()
            data = response.json()
            if current_only:
                current=data['current']
                return f"Current weather for {place['name']}, {place.get('country','')}: {current['temperature_2m']} °C as of {current['time']} local time. Source: Open-Meteo, https://open-meteo.com/."
            daily = data['daily']
            if when and when.isoformat() not in daily['time']:
                return f'The weather service did not return a forecast for {when.isoformat()}. Please try again later.'
            days = '; '.join(f"{date}: {daily['temperature_2m_min'][i]} to {daily['temperature_2m_max'][i]} °C, "
                             f"rain chance {daily['precipitation_probability_max'][i]}%"
                             for i,date in enumerate(daily['time']))
            return (f"Fresh forecast for {place['name']}, {place.get('country','')}. "
                    + (f"Current temperature {data['current']['temperature_2m']} °C as of {data['current']['time']} local time. " if not when else '') +
                    f"{days}. Source: Open-Meteo, https://open-meteo.com/.")
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return 'I could not retrieve the live weather forecast. Please try again shortly.'
    if re.search(r'\b(?:what is news|define news|meaning of news)\b',text,re.I):return None
    if not re.search(r'\b(news|headlines)\b', text, re.I):
        return None
    query = news_query(text, news_area)
    if query is None:
        return 'Which city or state would you like local news for? You can save it in Settings → News area, or ask for news in Mumbai or Maharashtra.'
    url = 'https://news.google.com/rss/search' if query else 'https://news.google.com/rss'
    try:
        response = requests.get(url, params={'q':query+' when:1d','hl':'en-IN','gl':'IN','ceid':'IN:en'} if query
                                else {'hl':'en-IN','gl':'IN','ceid':'IN:en'}, timeout=(3,5))
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError('Oversized feed')
        root = ElementTree.fromstring(response.content)
        headlines = []
        now = datetime.now(timezone.utc)
        for item in root.findall('./channel/item'):
            try:
                published = parsedate_to_datetime(item.findtext('pubDate',''))
                if not published.tzinfo or not 0 <= (now-published).total_seconds() <= 172800:
                    continue
            except (ValueError, TypeError):
                continue
            title = item.findtext('title','')[:250]
            source_element = item.find('source')
            source = item.findtext('source','News publisher')[:80]
            link = item.findtext('link','')
            if not link.startswith('https://news.google.com/'):
                continue
            source_url = source_element.get('url','') if source_element is not None else ''
            # Cite the retrieved article item, not an unrelated publisher homepage.
            citation = link
            headlines.append(f'{title} ({source}, {published.isoformat()}). Source: {citation}')
            if len(headlines) == 3:
                break
        india_now = now.astimezone(timezone(timedelta(hours=5, minutes=30)))
        bulletin_time = india_now.strftime('%d %B %Y, %I:%M %p') + ' IST.'
        return (bulletin_time + ' Recent headlines retrieved now: '+ ' '.join(headlines)) if headlines else 'No recent headlines were returned for that topic.'
    except (requests.RequestException, ValueError, ElementTree.ParseError):
        return 'I could not retrieve current news. Please try again shortly.'
