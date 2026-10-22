"""LinkedIn's supported OAuth/profile/post APIs, without browser-cookie scraping."""
import secrets
import threading
import time
from urllib.parse import urlencode

import requests
from agent_connections import secret_get,secret_set


class LinkedIn:
    def __init__(self):self.pending=None;self.lock=threading.Lock()
    def status(self):
        saved=secret_get('linkedin')
        return {'configured':bool(saved.get('client_id') and saved.get('client_secret')),
                'connected':bool(saved.get('access_token') and saved.get('expires_at',0)>time.time()),
                'scopes':saved.get('scopes',[]),'profile':saved.get('profile',{}),
                'messages':'Requires a connected provider with approved LinkedIn messaging access; not supplied by sign-in.',
                'jobs':'CV/job analysis and drafting are supported; job submission requires a provider exposing that action.'}
    def configure(self,client_id,client_secret,redirect_uri):
        if not client_id or len(client_id)>200 or not client_secret:raise ValueError('Enter your own LinkedIn developer app client ID and secret locally.')
        if not redirect_uri.startswith('http://127.0.0.1:') or not redirect_uri.endswith('/api/agent/linkedin/callback'):raise ValueError('Use the exact localhost callback shown in this panel.')
        secret_set('linkedin',{'client_id':client_id,'client_secret':client_secret,'redirect_uri':redirect_uri})
    def authorize(self):
        saved=secret_get('linkedin')
        if not saved.get('client_id') or not saved.get('client_secret'):raise ValueError('Configure your LinkedIn developer app first.')
        state=secrets.token_urlsafe(32)
        with self.lock:self.pending=(state,time.monotonic(),saved['redirect_uri'])
        return 'https://www.linkedin.com/oauth/v2/authorization?'+urlencode({
            'response_type':'code','client_id':saved['client_id'],'redirect_uri':saved['redirect_uri'],
            'state':state,'scope':'openid profile email w_member_social'})
    def callback(self,state,code):
        with self.lock:pending=self.pending;self.pending=None
        if not pending or not secrets.compare_digest(state,pending[0]) or time.monotonic()-pending[1]>600:raise ValueError('LinkedIn sign-in expired or the state did not match. Start Connect again.')
        saved=secret_get('linkedin')
        response=requests.post('https://www.linkedin.com/oauth/v2/accessToken',data={
            'grant_type':'authorization_code','code':code,'redirect_uri':pending[2],
            'client_id':saved['client_id'],'client_secret':saved['client_secret']},timeout=(5,20),allow_redirects=False)
        if response.status_code!=200:raise ValueError(f'LinkedIn token exchange failed (HTTP {response.status_code}). Check the app products and registered callback.')
        value=response.json()
        if not value.get('access_token'):raise ValueError('LinkedIn did not return an access token.')
        saved.update(access_token=value['access_token'],expires_at=time.time()+int(value.get('expires_in',0)),
                     scopes=str(value.get('scope','openid profile email w_member_social')).replace(',',' ').split())
        secret_set('linkedin',saved)
        return self.status()
    def _auth(self):
        saved=secret_get('linkedin')
        if not saved.get('access_token') or saved.get('expires_at',0)<=time.time():raise ValueError('Connect LinkedIn first; its authorization may have expired.')
        return saved,{'Authorization':'Bearer '+saved['access_token']}
    def profile(self):
        saved,headers=self._auth()
        response=requests.get('https://api.linkedin.com/v2/userinfo',headers=headers,timeout=(5,20),allow_redirects=False)
        if response.status_code!=200:raise ValueError(f'LinkedIn profile request failed (HTTP {response.status_code}). Check OpenID Connect access.')
        data=response.json();profile={key:data[key] for key in ('sub','name','given_name','family_name','email','picture') if key in data}
        saved['profile']=profile;secret_set('linkedin',saved)
        return profile
    def publish(self,text,visibility):
        saved,headers=self._auth()
        if 'w_member_social' not in saved.get('scopes',[]):raise ValueError('LinkedIn did not grant Share on LinkedIn permission.')
        person=saved.get('profile',{}).get('sub')
        if not person:raise ValueError('Approve a LinkedIn profile read first to identify the publishing account.')
        headers.update({'LinkedIn-Version':'202610','X-Restli-Protocol-Version':'2.0.0'})
        payload={'author':'urn:li:person:'+person,'commentary':text,'visibility':visibility,
                 'distribution':{'feedDistribution':'MAIN_FEED','targetEntities':[],'thirdPartyDistributionChannels':[]},
                 'lifecycleState':'PUBLISHED','isReshareDisabledByAuthor':False}
        response=requests.post('https://api.linkedin.com/rest/posts',headers=headers,json=payload,timeout=(5,20),allow_redirects=False)
        if response.status_code!=201:raise ValueError(f'LinkedIn did not confirm publication (HTTP {response.status_code}). Check the account before retrying; a timed-out write is not retried automatically.')
        return {'published':True,'post_id':response.headers.get('x-restli-id'),'account':saved.get('profile',{}).get('name')}
    def disconnect(self):
        with self.lock:self.pending=None
        secret_set('linkedin',{})


linkedin=LinkedIn()
