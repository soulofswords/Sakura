"""Google Workspace tools. All calls enter through Agent's existing review gate."""
import hashlib
import json
import re
from urllib.parse import quote
import requests
from agent_calendar import google_calendar, DRIVE_SCOPE
from agent_connections import secret_get

def binding():
    saved=secret_get('google-calendar')
    return hashlib.sha256(json.dumps([google_calendar.config_fingerprint(),saved.get('refresh_token',''),saved.get('scopes',[])],sort_keys=True).encode()).hexdigest()

def request(service,method,path,params=None,body=None):
    saved,headers=google_calendar._auth()
    if DRIVE_SCOPE not in saved.get('scopes',[]):raise ValueError('Reconnect Google and approve Drive, Docs and Sheets access first.')
    roots={'drive':'https://www.googleapis.com/drive/v3','docs':'https://docs.googleapis.com/v1','sheets':'https://sheets.googleapis.com/v4'}
    with requests.request(method,roots[service]+path,headers=headers,params=params,json=body,timeout=(5,25),allow_redirects=False,stream=True) as response:
        if response.status_code not in (200,201):raise ValueError(f'Google {service} returned HTTP {response.status_code}. Check permissions and enabled APIs. No write was retried.')
        data=bytearray()
        for chunk in response.iter_content(8192):
            data.extend(chunk)
            if len(data)>2_000_000:raise ValueError('Google response is too large. Request a smaller range or fewer files.')
        return json.loads(data)

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value):raise ValueError('Use an actual Google file ID returned by Drive search or supplied by the user.')
    return value

def execute(tool,args):
    if tool=='google.drive.search':
        name=args.get('name','').replace('\\','\\\\').replace("'","\\'")
        query="trashed = false"+(" and name contains '"+name+"'" if name else '')
        return request('drive','GET','/files',{'q':query,'pageSize':25,'fields':'files(id,name,mimeType,webViewLink),nextPageToken'})
    file_id=identifier(args['file_id'])
    if tool=='google.drive.rename':return request('drive','PATCH','/files/'+file_id,body={'name':args['name']})
    if tool=='google.docs.read':return request('docs','GET','/documents/'+file_id)
    if tool=='google.docs.append':
        return request('docs','POST','/documents/'+file_id+':batchUpdate',body={'requests':[{'insertText':{'endOfSegmentLocation':{},'text':args['text']}}]})
    cell_range=quote(args.get('range',''),safe='')
    if tool=='google.sheets.read':return request('sheets','GET','/spreadsheets/'+file_id+'/values/'+cell_range)
    if tool=='google.sheets.write':return request('sheets','PUT','/spreadsheets/'+file_id+'/values/'+cell_range,{'valueInputOption':'RAW'}, {'range':args['range'],'majorDimension':'ROWS','values':args['values']})
    raise ValueError('Unsupported Google tool.')

ID={'type':'string','minLength':1,'maxLength':200};RANGE={'type':'string','minLength':1,'maxLength':200}
def tool(name,description,properties,required):
    return {'name':name,'description':description+' Requires explicit action approval.','inputSchema':{'type':'object','properties':properties,'required':required,'additionalProperties':False}}
TOOLS=[
 tool('google.drive.search','Find up to 25 files by name; returns real IDs.',{'name':{'type':'string','maxLength':200}},[]),
 tool('google.drive.rename','Rename one Drive file. Show exact file ID and new name.',{'file_id':ID,'name':{'type':'string','minLength':1,'maxLength':200}},['file_id','name']),
 tool('google.docs.read','Read one Google Docs document.',{'file_id':ID},['file_id']),
 tool('google.docs.append','Append the exact reviewed text to the end of a Google Doc.',{'file_id':ID,'text':{'type':'string','minLength':1,'maxLength':20000}},['file_id','text']),
 tool('google.sheets.read','Read an explicit A1 range in a Google spreadsheet.',{'file_id':ID,'range':RANGE},['file_id','range']),
 tool('google.sheets.write','Replace cell values in an exact A1 range. Values are RAW, not formulas. Show every value for approval.',{'file_id':ID,'range':RANGE,'values':{'type':'array','minItems':1,'maxItems':100,'items':{'type':'array','maxItems':50,'items':{'type':['string','number','boolean','null'],'maxLength':2000}}}},['file_id','range','values']),
]
