"""Authorize only Drive files created by Sakura's publisher, not the owner's inbox."""
import argparse
import base64
import hashlib
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
import secrets
import sys
import time
from urllib.parse import urlencode,urlsplit,parse_qs
import webbrowser
import requests


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',required=True);args=parser.parse_args()
    sys.path.insert(0,args.app)
    if list(Path(args.app).glob('sakura_core*.pyd')):__import__('sakura_core')
    from agent_connections import secret_get,secret_set
    saved=secret_get('google-calendar')
    if not saved.get('client_id'):raise ValueError('Google OAuth client is not configured.')
    state=secrets.token_urlsafe(24);verifier=secrets.token_urlsafe(48)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    received={}
    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            query=parse_qs(urlsplit(self.path).query)
            if query.get('state',[''])[0]!=state:self.send_error(400);return
            received.update(code=query.get('code',[''])[0],error=query.get('error',[''])[0])
            self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
            self.wfile.write(b'<h2>Return to Sakura. The publisher is checking your authorization.</h2>')
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',8793),Callback);server.timeout=1
    redirect='http://127.0.0.1:8793/'
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({
        'client_id':saved['client_id'],'redirect_uri':redirect,'response_type':'code',
        'scope':'https://www.googleapis.com/auth/drive.file','access_type':'offline','prompt':'consent',
        'include_granted_scopes':'false','state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
    webbrowser.open(url)
    print('Opened Google consent limited to Drive files created by the publisher.',flush=True)
    deadline=time.monotonic()+600
    try:
        while not received and time.monotonic()<deadline:server.handle_request()
    finally:server.server_close()
    if not received.get('code'):raise ValueError('Storage authorization was not completed.')
    reply=requests.post('https://oauth2.googleapis.com/token',data={
        'client_id':saved['client_id'],'client_secret':saved.get('client_secret',''),'code':received['code'],
        'code_verifier':verifier,'redirect_uri':redirect,'grant_type':'authorization_code'},timeout=30)
    if reply.status_code!=200:raise ValueError('Could not complete storage authorization.')
    data=reply.json();scopes=set(data.get('scope','').split())
    if scopes!={'https://www.googleapis.com/auth/drive.file'} or not data.get('refresh_token'):
        raise ValueError('Google did not return the isolated Drive-file grant. No account credential was uploaded.')
    secret_set('library-storage-google',{'client_id':saved['client_id'],'client_secret':saved.get('client_secret',''),
        'refresh_token':data['refresh_token'],'scope':'https://www.googleapis.com/auth/drive.file'})
    print('Dedicated storage authorization saved in encrypted local storage.',flush=True)


if __name__=='__main__':main()
