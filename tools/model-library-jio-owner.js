// Owner setup/publisher. Only the proof HASH is injected at deployment;
// the random owner capability stays DPAPI encrypted on the publisher PC.
const OWNER_PROOF_HASH='REPLACE_OWNER_PROOF_HASH';
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
async function ownerHandle(request){
  if(request.method!=='POST')return json({error:'Use POST.'},405);
  const proof=request.headers.get('X-Sakura-Owner')||'';
  if(!/^[A-Za-z0-9_-]{64}$/.test(proof))return json({error:'Owner authorization required.'},401);
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(proof)))].map(x=>x.toString(16).padStart(2,'0')).join('');
  if(hash!==OWNER_PROOF_HASH)return json({error:'Owner authorization required.'},401);
  const project=Deno.env.get('SUPABASE_URL'),admin=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  const headers={apikey:admin,Authorization:'Bearer '+admin,'Content-Type':'application/json'};
  const raw=await request.text();if(raw.length>64000)return json({error:'Request too large.'},413);
  const body=JSON.parse(raw);
  const account=body.account||'primary';
  if(!['primary','account2'].includes(account))return json({error:'Unknown storage account.'},400);
  if(body.operation==='configure'){
    const secret=body.storage,session=secret?.session;
    if(secret?.provider!=='jio'||!session?.twoFAValidated||!jioRegions[session.dcGroupCode])return json({error:'Verified storage required.'},400);
    const profile=await fetch('https://api.jioaicloud.com/security/users',{
      headers:await jioHeaders(session),redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!profile.ok||(await profile.json()).userId!==session.userId)return json({error:'Jio account verification failed.'},403);
    const previous=await jioRpc(project,headers,'sakura_library_jio_read');
    if(account==='account2'&&previous?.session?.userId===session.userId)return json({error:'Choose a different second Jio account.'},409);
    if(account==='account2'&&previous?.provider!=='jio')return json({error:'Connect primary storage first.'},409);
    const merged=account==='primary'?{...secret,accounts:previous?.accounts||{}}:{...previous,accounts:{...previous.accounts,[account]:secret}};
    await jioRpc(project,headers,'sakura_library_jio_write',{payload:merged});
    return json({configured:true});
  }
  if(body.operation!=='publish')return json({error:'Unknown operation.'},400);
  const entry=body.model;
  if(!entry||!/^[-A-Za-z0-9_]{1,100}$/.test(entry.id)||!['pmx','live2d','vrm'].includes(entry.format)||
    typeof entry.name!=='string'||entry.name.length<1||entry.name.length>200||
    !Number.isInteger(entry.bytes)||entry.bytes<1||entry.bytes>536870912||!/^([a-f0-9]{64})$/.test(entry.sha256)||
    !/^[-A-Za-z0-9_]{1,200}$/.test(entry.jio_object_key)||
    (entry.jio_preview_object_key&&!/^[-A-Za-z0-9_]{1,200}$/.test(entry.jio_preview_object_key)))return json({error:'Invalid catalogue entry.'},400);
  const stored=await jioRpc(project,headers,'sakura_library_jio_read');
  if(stored?.provider!=='jio')return json({error:'Configure storage first.'},409);
  const selected=account==='primary'?stored:stored.accounts?.[account];
  if(!selected?.session)return json({error:'Connect this storage account first.'},409);
  const origin='https://'+jioRegions[selected.session.dcGroupCode]+'-api.jioaicloud.com';
  for(const [key,size]of [[entry.jio_object_key,entry.bytes],[entry.jio_preview_object_key,null]]){
    if(!key)continue;
    const response=await fetch(origin+'/nms/metadata/'+encodeURIComponent(key)+'/info',{
      headers:await jioHeaders(selected.session),redirect:'error',signal:AbortSignal.timeout(15000)});
    if(!response.ok)return json({error:'Stored asset could not be verified.'},409);
    const asset=await response.json();
    if(asset.objectOwnerUserId!==selected.session.userId||asset.parentObjectKey!==body.folderKey||
      (size!==null&&asset.sizeInBytes!==size)||(size===null&&asset.sizeInBytes>8000000))return json({error:'Stored asset owner, size or folder mismatch.'},409);
  }
  const row={id:entry.id,name:entry.name,format:entry.format,bytes:entry.bytes,sha256:entry.sha256,
    version:entry.sha256.slice(0,12),mobile_compatible:entry.mobile_compatible===true,published:true,
    jio_object_key:(account==='primary'?'':account+'__')+entry.jio_object_key,jio_preview_object_key:entry.jio_preview_object_key?((account==='primary'?'':account+'__')+entry.jio_preview_object_key):null,
    drive_file_id:null,preview_drive_file_id:null,storage_path:null,preview_storage_path:null};
  const response=await fetch(project+'/rest/v1/sakura_model_catalogue?on_conflict=id',{
    method:'POST',headers:{...headers,Prefer:'resolution=merge-duplicates'},body:JSON.stringify(row),
    redirect:'error',signal:AbortSignal.timeout(15000)});
  return response.ok?json({published:entry.id}):json({error:'Catalogue write failed.'},503);
}
Deno.serve(request=>ownerHandle(request).catch(()=>json({error:'Owner request could not complete.'},503)));
