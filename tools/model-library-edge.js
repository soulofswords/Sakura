// Supabase Edge Function: sakura-library. No owner credentials in client code.
const responseJSON = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {'Content-Type':'application/json','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
});
async function handle(request) {
  if (request.method !== 'GET') return responseJSON({error:'Use GET.'}, 405);
  const project = Deno.env.get('SUPABASE_URL');
  const admin = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  const authorization = request.headers.get('Authorization') || '';
  if (!project || !admin) return responseJSON({error:'Library host is not configured.'}, 503);
  if (!authorization.startsWith('Bearer ') || authorization.length > 8200) return responseJSON({error:'Sign into Sakura first.'}, 401);
  const userResponse = await fetch(project + '/auth/v1/user', {
    headers:{apikey:admin, Authorization:authorization}, redirect:'error', signal:AbortSignal.timeout(15000)
  });
  if (!userResponse.ok) return responseJSON({error:'Your Sakura session has expired.'}, 401);
  const user = await userResponse.json();
  if (!user.id || !user.email_confirmed_at) return responseJSON({error:'Confirm your Sakura account email first.'}, 403);
  const path = new URL(request.url).pathname.replace(/^.*\/sakura-library/, '');
  const base = project + '/rest/v1/sakura_model_catalogue?published=eq.true';
  const headers = {apikey:admin, Authorization:'Bearer ' + admin};
  if (path === '/v1/models') {
    const catalogue=[];
    for(let offset=0;offset<=2000;offset+=500){
      const rows=await fetch(base+'&select=id,name,format,bytes,sha256,version,mobile_compatible,preview_storage_path,preview_drive_file_id,jio_preview_object_key&order=name.asc,id.asc&limit=500&offset='+offset,{
        headers,redirect:'error',signal:AbortSignal.timeout(15000)
      });
      if(!rows.ok)return responseJSON({error:'The model catalogue is not ready yet.'},503);
      const page=await rows.json();
      if(!Array.isArray(page))return responseJSON({error:'Invalid model catalogue.'},503);
      catalogue.push(...page);
      if(catalogue.length>2000)return responseJSON({error:'The library catalogue exceeds this client version. Update Sakura.'},503);
      if(page.length<500)break;
    }
    const models=catalogue.map(({preview_storage_path,preview_drive_file_id,jio_preview_object_key,...model})=>({
      ...model,preview:!!(preview_storage_path||preview_drive_file_id||jio_preview_object_key)
    }));
    return responseJSON({models});
  }
  const match = path.match(/^\/v1\/models\/([A-Za-z0-9_-]{1,100})\/(package|preview)$/);
  if (!match) return responseJSON({error:'Not found.'}, 404);
  const preview=match[2]==='preview';
  const columns=preview?'preview_drive_file_id,preview_storage_path,jio_preview_object_key':'drive_file_id,storage_path,jio_object_key,bytes';
  const rowResponse = await fetch(base + '&id=eq.' + match[1] + '&select='+columns+'&limit=1', {
    headers, redirect:'error', signal:AbortSignal.timeout(15000)
  });
  if (!rowResponse.ok) return responseJSON({error:'Cannot read this model.'}, 503);
  const entry = (await rowResponse.json())[0];
  if (!entry) return responseJSON({error:'Model is not published.'}, 404);
  const storagePath=preview?entry.preview_storage_path:entry.storage_path;
  const driveID=preview?entry.preview_drive_file_id:entry.drive_file_id;
  const jioID=preview?entry.jio_preview_object_key:entry.jio_object_key;
  let file;
  const storagePattern=preview?/^[A-Za-z0-9_/-]+\.webp$/:/^[A-Za-z0-9_/-]+\.zip$/;
  if(jioID){
    file=await jioFile(project,headers,jioID);
  } else if (storagePath && storagePattern.test(storagePath) && !storagePath.includes('..')) {
    file = await fetch(project + '/storage/v1/object/' + storagePath, {headers,redirect:'error',signal:AbortSignal.timeout(120000)});
  } else if (driveID && /^[A-Za-z0-9_-]{1,200}$/.test(driveID)) {
    let clientID = Deno.env.get('SAKURA_DRIVE_OAUTH_CLIENT_ID');
    let clientSecret = Deno.env.get('SAKURA_DRIVE_OAUTH_CLIENT_SECRET');
    let refreshToken = Deno.env.get('SAKURA_DRIVE_REFRESH_TOKEN');
    if(!clientID||!clientSecret||!refreshToken){
      const stored=await fetch(project+'/rest/v1/rpc/sakura_library_storage_read',{
        method:'POST',headers:{...headers,'Content-Type':'application/json'},body:'{}',redirect:'error',signal:AbortSignal.timeout(15000)
      });
      if(stored.ok){const secret=await stored.json();if(secret?.scope==='https://www.googleapis.com/auth/drive.file'){
        clientID=secret.client_id;clientSecret=secret.client_secret;refreshToken=secret.refresh_token;
      }}
    }
    if (!clientID || !clientSecret || !refreshToken) return responseJSON({error:'The owner has not connected private model storage yet.'}, 503);
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method:'POST',body:new URLSearchParams({client_id:clientID,client_secret:clientSecret,refresh_token:refreshToken,grant_type:'refresh_token'}),
      redirect:'error',signal:AbortSignal.timeout(15000)
    });
    if (!tokenResponse.ok) return responseJSON({error:'Model storage authorization needs attention.'}, 503);
    const accessToken = (await tokenResponse.json()).access_token;
    file = await fetch('https://www.googleapis.com/drive/v3/files/' + driveID + '?alt=media', {
      headers:{Authorization:'Bearer ' + accessToken},redirect:'error',signal:AbortSignal.timeout(120000)
    });
  } else return responseJSON({error:'The model package is not ready yet.'}, 503);
  if (!file.ok || !file.body) return responseJSON({error:'Cannot download this model right now.'}, 503);
  let received = 0;
  const stream = file.body.pipeThrough(new TransformStream({
    transform(chunk, controller) {
      received += chunk.byteLength;
      if (received > (preview?8000000:entry.bytes) || received > 536870912) throw new Error('Asset size exceeded.');
      controller.enqueue(chunk);
    },
    flush() { if (!preview && received !== entry.bytes) throw new Error('Incomplete package.'); }
  }));
  return new Response(stream, {headers:{'Content-Type':preview?'image/webp':'application/zip','Cache-Control':'private, no-store',
    'X-Content-Type-Options':'nosniff','Content-Disposition':(preview?'inline':'attachment')+'; filename="' + match[1] + (preview?'.webp':'.zip')+'"'}});
}
Deno.serve(request => handle(request).catch(() => responseJSON({error:'The library request could not complete.'}, 503)));
