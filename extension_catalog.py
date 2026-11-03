"""Curated, version-pinned MCP cards. Adding is configuration, not execution."""
from pathlib import Path
import copy

CATALOG=[
 {'id':'google-calendar','name':'Google Calendar','publisher':'Sakura adapter','source':'https://developers.google.com/calendar','description':'Connect the account you approve to read and review calendar actions.','transport':'builtin','service':'google-calendar'},
 {'id':'google-drive','name':'Google Drive, Docs & Sheets','publisher':'Sakura adapter','source':'https://developers.google.com/drive','description':'Use the Google services you authorize; writes still follow action approvals.','transport':'builtin','service':'google-drive'},
 {'id':'linkedin','name':'LinkedIn','publisher':'Sakura adapter','source':'https://learn.microsoft.com/en-us/linkedin/','description':'Uses the LinkedIn API permissions your application/account has actually been granted.','transport':'builtin','service':'linkedin'},
 {'id':'playwright','name':'Playwright MCP','publisher':'Microsoft / Playwright','source':'https://github.com/microsoft/playwright-mcp','description':'Third-party browser automation. Discovery launches its Node package only after approval. Its own capabilities and limits differ from Sakura’s isolated browser.','transport':'stdio','package':'@playwright/mcp@0.0.84','args':['--headless','--isolated']},
 {'id':'filesystem','name':'Filesystem MCP','publisher':'MCP reference server','source':'https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem','description':'Third-party filesystem tools for one explicitly selected existing folder. Discovery launches the package after approval. Workspace restrictions are not an OS sandbox.','transport':'stdio','package':'@modelcontextprotocol/server-filesystem@2.1.0','workspace':True},
]

def cards():return copy.deepcopy(CATALOG)

def configuration(identifier,workspace=''):
    card=next((c for c in CATALOG if c['id']==identifier),None)
    if not card:raise ValueError('Choose a published extension card.')
    if card['transport']=='builtin':return {'name':card['name'],'transport':'builtin','service':card['service']}
    args=['--yes',card['package'],*card.get('args',[])]
    if card.get('workspace'):
        if not isinstance(workspace,str) or not workspace.strip():raise ValueError('Choose the folder this extension may access.')
        path=Path(workspace).expanduser().resolve(strict=True)
        if not path.is_dir():raise ValueError('Choose an existing folder.')
        args.append(str(path))
    return {'name':card['name'],'transport':'stdio','command':'npx','args':args}
