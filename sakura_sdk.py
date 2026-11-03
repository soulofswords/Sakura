"""Minimal local-only Sakura client and CLI. Set SAKURA_SDK_TOKEN in your environment."""
import argparse
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,ProxyHandler


class Sakura:
    def __init__(self,base_url='http://127.0.0.1:8766',token=None):
        parts=urlsplit(base_url)
        if parts.scheme!='http' or parts.hostname not in ('127.0.0.1','::1','localhost') or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('','/'):
            raise ValueError('SDK only connects to the local Sakura loopback address.')
        self.base=base_url.rstrip('/');self.token=token or os.environ.get('SAKURA_SDK_TOKEN','')
        if not self.token:raise ValueError('Create a SDK token in Sakura and set SAKURA_SDK_TOKEN. Never paste it in chat.')
    def chat(self,text):
        request=Request(self.base+'/api/sdk/chat',data=json.dumps({'text':text}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+self.token,'Origin':self.base},method='POST')
        # Do not send a local access token through an ambient proxy or redirect.
        from urllib.request import HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=120) as response:
            return json.loads(response.read(1_000_000))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('message');parser.add_argument('--url',default='http://127.0.0.1:8766')
    args=parser.parse_args();print(Sakura(args.url).chat(args.message)['reply'])
