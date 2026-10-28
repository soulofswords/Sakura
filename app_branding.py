"""Distinct product identity, with a mode icon inside Companion."""
from pathlib import Path
import json
import re


def icon_path(root, edition, tracking=False):
    name='vtuber' if edition=='vtuber' else 'companion-vtuber' if tracking else 'companion'
    return Path(root)/'launcher'/(name+'.ico')


def edition_html(text,edition):
    """Use the installed product identity even when shared HTML was refreshed."""
    edition=edition if edition in ('vtuber','companion','combined') else 'combined'
    if edition=='vtuber':
        text=re.sub(r'<title>[^<]*</title>','<title>Sakura VTuber</title>',text,count=1)
        text=text.replace('<strong>Sakura Companion</strong>','<strong>Sakura VTuber</strong>')
        text=text.replace('alt="Sakura Companion"','alt="Sakura VTuber"')
        text=text.replace('alt="Sakura Desktop Companion"','alt="Sakura VTuber"')
        text=text.replace('/static/assets/desktop-companion.png','/static/assets/vtuber-app.png')
        text=text.replace('/static/assets/companion-vtuber.png','/static/assets/vtuber-app.png')
        text=text.replace('<span class="badge">Companion</span>','<span class="badge">VTuber</span>')
    # Place this after any generated edition script, before body scripts run.
    script='<script>window.SAKURA_EDITION='+json.dumps(edition)+';</script>'
    return text.replace('</head>',script+'</head>',1)
