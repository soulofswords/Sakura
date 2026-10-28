// Server-side Jio reader. Concatenate before model-library-edge.js at deployment.
// No owner credentials, provider object IDs or storage URLs enter client responses.
const jioRegions={JAWS:'jaws',JMNG:'jmng1',JMNG2:'jmng2'};
let jioPublicHeaders=null;
async function jioHeaders(session){
  if(!jioPublicHeaders){
    const r=await fetch('https://www.jioaicloud.com/assets/runtime-config.json',{redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!r.ok)throw Error('Jio configuration unavailable');
    const data=(await r.json()).envHeaders;
    if(!data||!['X-Api-Key','X-App-Secret'].every(k=>typeof data[k]==='string'&&data[k].length<512&&!/[\r\n]/.test(data[k])))throw Error('Jio configuration changed');
    jioPublicHeaders={'X-Api-Key':data['X-Api-Key'],'X-App-Secret':data['X-App-Secret'],
      'X-Client-Details':'clientType:WEB; appVersion:3.0.0','X-Device-Type':'W',
      'Accept-Language':'en','Accept':'application/json','Content-Type':'application/json'};
  }
  if(!session?.authToken?.accessToken||!session.userId||!session.deviceKey||!jioRegions[session.dcGroupCode])throw Error('Jio authorization missing');
  return {...jioPublicHeaders,Authorization:'Basic '+btoa(session.authToken.accessToken),
    'X-User-Id':session.userId,'X-Device-Key':session.deviceKey};
}
async function jioRpc(project,headers,name,payload={}){
  const response=await fetch(project+'/rest/v1/rpc/'+name,{method:'POST',headers:{...headers,'Content-Type':'application/json'},
    body:JSON.stringify(payload),redirect:'error',signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw Error('Private Jio configuration unavailable');
  return response.status===204?null:response.json();
}
async function jioFile(project,headers,objectKey){
  if(typeof objectKey!=='string'||!/^[-A-Za-z0-9_]{1,200}$/.test(objectKey))throw Error('Invalid private object');
  const secret=await jioRpc(project,headers,'sakura_library_jio_read');
  let account='primary';
  if(objectKey.startsWith('account2__')){account='account2';objectKey=objectKey.slice(10);}
  if(secret?.provider!=='jio')throw Error('Jio not configured');
  const session=account==='primary'?secret.session:secret.accounts?.[account]?.session;
  if(!session)throw Error('Storage account not connected');
  const request=()=>fetch('https://'+jioRegions[session.dcGroupCode]+'-dl.jioaicloud.com/download/files/'+encodeURIComponent(objectKey),
    {headers:awaitableHeaders,redirect:'error',signal:AbortSignal.timeout(120000)});
  let awaitableHeaders=await jioHeaders(session);
  let response=await request();
  if(response.status===401||response.status===403){
    await response.body?.cancel();
    if(!session.authToken.refreshToken)throw Error('Jio reconnection required');
    const refreshed=await fetch('https://api.jioaicloud.com/account/token/refresh',{
      method:'PUT',headers:awaitableHeaders,body:JSON.stringify({refreshToken:session.authToken.refreshToken,deviceType:'W',
        jToken:true,isIdamOn:'true',isStaySignIn:true,deviceInfo:{model:'browser',deviceName:'Web Device',type:'browser',isWebClient:true,deviceKey:session.deviceKey}}),
      redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!refreshed.ok)throw Error('Jio reconnection required');
    const body=await refreshed.json(),token=body.authToken||body;
    if(typeof token.accessToken!=='string'||!token.accessToken)throw Error('Invalid Jio refresh');
    session.authToken={...session.authToken,...token};
    const updated=account==='primary'?{...secret,session}:{...secret,accounts:{...secret.accounts,[account]:{...secret.accounts[account],session}}};
    await jioRpc(project,headers,'sakura_library_jio_write',{payload:updated});
    awaitableHeaders=await jioHeaders(session);
    response=await request();
  }
  return response;
}
