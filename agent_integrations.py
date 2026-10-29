"""Curated Agent integrations, exposed through the normal reviewed tool runtime."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile
import requests
from config import BASE_DIR
from agent_connections import secret_get,secret_set

ROOT=BASE_DIR/'agent-integrations'
REPOS={'playwright':'https://github.com/microsoft/playwright','firecrawl':'https://github.com/firecrawl/firecrawl','nuclei':'https://github.com/projectdiscovery/nuclei'}

def schema(properties,required=()):return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
TOOLS=[
 {'name':'integrations.status','description':'Check installed Playwright, configured Firecrawl and Nuclei. Never claim setup succeeded without this status.','inputSchema':schema({})},
 {'name':'integrations.setup','description':'Install or prepare Playwright, Firecrawl or Nuclei on user request. Downloads are reviewed. Firecrawl requires the user to enter a key in Connections; do not ask for secrets in chat.','inputSchema':schema({'provider':{'type':'string','enum':list(REPOS)}},['provider'])},
 {'name':'firecrawl.scrape','description':'Extract one public website as Markdown through the configured Firecrawl cloud API. Sends the URL to Firecrawl and can consume provider credits.','inputSchema':schema({'url':{'type':'string','maxLength':2000}},['url'])},
 {'name':'firecrawl.search','description':'Search the web through Firecrawl. Sends the query to Firecrawl and can consume provider credits.','inputSchema':schema({'query':{'type':'string','minLength':1,'maxLength':300}},['query'])},
 {'name':'nuclei.scan','description':'Run a bounded signed HTTP-template security scan only against an exact origin the user has authorized in Connections. No arbitrary flags, code templates, fuzzing or out-of-band callbacks.','inputSchema':schema({'url':{'type':'string','maxLength':2000}},['url'])},
 {'name':'mcp.add','description':'Add and discover a user-requested MCP server after review. Stdio starts the executable shown. Never embed credentials in tool arguments; configure secrets in Connections.','inputSchema':schema({'name':{'type':'string','minLength':1,'maxLength':80},'transport':{'type':'string','enum':['http','stdio']},'url':{'type':'string','maxLength':2000},'command':{'type':'string','maxLength':500},'args':{'type':'array','items':{'type':'string','maxLength':2000},'maxItems':30}},['name','transport'])},
]
NAMES={item['name'] for item in TOOLS}

def nuclei_path():return ROOT/'nuclei'/('nuclei.exe' if sys.platform=='win32' else 'nuclei')

def status():
    settings=secret_get('integrations')
    browsers=[shutil.which(name) for name in ('msedge','google-chrome','chromium')]
    if sys.platform=='win32':browsers += [str(Path(os.environ.get(key,''))/'Microsoft/Edge/Application/msedge.exe') for key in ('ProgramFiles','ProgramFiles(x86)')]
    playwright=importlib.util.find_spec('playwright') is not None
    browser=any(path and Path(path).is_file() for path in browsers)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as client:browser=browser or Path(client.chromium.executable_path).is_file()
    except Exception:pass
    return {'playwright':{'installed':playwright,'ready':playwright and browser,'repository':REPOS['playwright']},
        'firecrawl':{'configured':bool(settings.get('firecrawl_key')),'ready':bool(settings.get('firecrawl_key')),'repository':REPOS['firecrawl']},
        'nuclei':{'installed':nuclei_path().is_file(),'ready':nuclei_path().is_file() and bool(settings.get('scan_origins')),'origins':settings.get('scan_origins',[]),'repository':REPOS['nuclei']}}

def origin(url):
    parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password or parts.fragment:raise ValueError('Use a complete HTTP(S) URL without credentials or fragments.')
    host=parts.hostname.casefold()
    if ':' in host:host='['+host+']'
    port=parts.port
    return parts.scheme+'://'+host+(':'+str(port) if port and port!={'http':80,'https':443}[parts.scheme] else '')

def configure(payload):
    settings=secret_get('integrations')
    if payload.get('clear_firecrawl'):settings.pop('firecrawl_key',None)
    if payload.get('firecrawl_key'):
        key=payload['firecrawl_key']
        if not isinstance(key,str) or len(key)>1000 or any(char.isspace() for char in key):raise ValueError('Enter a valid Firecrawl key.')
        settings['firecrawl_key']=key
    if 'scan_origins' in payload:
        values=payload['scan_origins']
        if not isinstance(values,list) or len(values)>20:raise ValueError('Authorize up to 20 exact origins.')
        settings['scan_origins']=list(dict.fromkeys(origin(value) for value in values))
    secret_set('integrations',settings)
    return status()

def download(url,limit,redirects=0):
    if redirects>5:raise ValueError('Too many integration download redirects.')
    host=urlsplit(url).hostname
    if urlsplit(url).scheme!='https' or host not in ('api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):raise ValueError('Unexpected integration download origin.')
    with requests.get(url,headers={'User-Agent':'Sakura-Agent'},stream=True,timeout=(10,45),allow_redirects=False) as response:
        if response.status_code in (301,302,303,307,308):return download(response.headers.get('Location',''),limit,redirects+1)
        if response.status_code!=200:raise ValueError('Integration download failed (HTTP '+str(response.status_code)+').')
        data=bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data)>limit:raise ValueError('Integration download exceeded its size limit.')
        return bytes(data)

def setup(provider,run_process):
    if provider=='firecrawl':return {'ok':True,'configured':status()['firecrawl']['configured'],'requires_user_input':'Enter your Firecrawl key in Agent Connections > Web & security tools. No key is requested through chat.'}
    if provider=='playwright':
        if status()['playwright']['ready']:return {'ok':True,'ready':True,'tools':'browser.open, browser.snapshot, browser.click, browser.fill, browser.close'}
        if importlib.util.find_spec('playwright') is None:raise ValueError('Playwright is missing from this Sakura installation. Repair its required dependencies.')
        result=run_process([sys.executable,'-m','playwright','install','chromium'],str(BASE_DIR),timeout=300)
        if not result.get('ok'):return result
        return {'ok':status()['playwright']['ready'],'state':status()['playwright']}
    if provider!='nuclei':raise ValueError('Unknown integration.')
    if nuclei_path().is_file():return {'ok':True,'installed':True,'note':'Authorize scan origins in Connections before scanning.'}
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):raise ValueError('Automatic Nuclei installation currently supports Windows x64. Other platforms need an explicit package implementation.')
    release=json.loads(download('https://api.github.com/repos/projectdiscovery/nuclei/releases/latest',2_000_000))
    assets=release.get('assets',[]);package=next((a for a in assets if a['name'].endswith('windows_amd64.zip')),None);checks=next((a for a in assets if a['name'].endswith('checksums.txt')),None)
    if not package or not checks:raise ValueError('Official Nuclei package/checksums are unavailable.')
    checksums=download(checks['browser_download_url'],2_000_000).decode()
    expected=next((line.split()[0] for line in checksums.splitlines() if len(line.split())==2 and line.split()[1].lstrip('*')==package['name']),None)
    data=download(package['browser_download_url'],100_000_000)
    if not expected or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Nuclei checksum mismatch; nothing installed.')
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members=[item for item in archive.infolist() if item.filename=='nuclei.exe']
        if len(members)!=1 or members[0].file_size>200_000_000:raise ValueError('Invalid Nuclei executable package.')
        target=nuclei_path();target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as pending:
            temporary=Path(pending.name);pending.write(archive.read(members[0]))
        try:temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
    return {'ok':True,'installed':True,'version':release['tag_name'],'sha256':expected,'note':'Authorize scan origins in Connections before scanning.'}

def firecrawl(tool,args):
    key=secret_get('integrations').get('firecrawl_key')
    if not key:raise ValueError('Firecrawl needs your API key. Enter it in Agent Connections > Web & security tools.')
    scrape=tool=='firecrawl.scrape'
    if scrape:
        from agent_web import _vetted
        _vetted(args['url'])
    body={'url':args['url'],'formats':['markdown'],'onlyMainContent':True} if scrape else {'query':args['query'],'limit':5}
    with requests.post('https://api.firecrawl.dev/v2/'+('scrape' if scrape else 'search'),headers={'Authorization':'Bearer '+key},json=body,timeout=(10,60),allow_redirects=False,stream=True) as response:
        if response.status_code!=200:raise ValueError('Firecrawl request failed (HTTP '+str(response.status_code)+'). Check the saved key and provider credits.')
        content=bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content)>1_000_000:raise ValueError('Firecrawl returned too much data.')
        data=json.loads(content)
    return {'ok':data.get('success',False),'data':json.dumps(data.get('data',''),ensure_ascii=False)[:30000],'provider':'Firecrawl'}

def execute(tool,args,runtime,cancel_event=None):
    from agent_runtime import run_process
    if tool=='integrations.status':return {'ok':True,**status()}
    if tool=='integrations.setup':return setup(args['provider'],run_process)
    if tool.startswith('firecrawl.'):return firecrawl(tool,args)
    if tool=='mcp.add':
        config=runtime.connections.save(args)
        from agent_connections import mcp_request
        try:
            tools=mcp_request(config,'discover');runtime.connections.tools[config['id']]=tools
            return {'ok':True,'connection':config,'discovered_tools':[item['name'] for item in tools]}
        except Exception:return {'ok':False,'configured':True,'connection':config,'error':'Connection saved but discovery failed. Check server dependencies and credentials in Connections; no success was assumed.'}
    if tool=='nuclei.scan':
        if origin(args['url']) not in secret_get('integrations').get('scan_origins',[]):raise ValueError('Authorize this exact origin in Agent Connections before scanning.')
        if not nuclei_path().is_file():raise ValueError('Install Nuclei through integrations.setup first.')
        command=[str(nuclei_path()),'-u',args['url'],'-pt','http','-dut','-ni','-duc','-rl','5','-c','2','-timeout','10','-retries','0','-jsonl','-silent','-etags','dos,fuzz,bruteforce,headless,code']
        return run_process(command,str(nuclei_path().parent),timeout=120,cancel_event=cancel_event)
    raise ValueError('Unknown integration tool.')
