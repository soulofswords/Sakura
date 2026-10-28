const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 let serve,refreshes=0,expired=false,mode='valid',calls=[];
 const session={userId:'private-owner',deviceKey:'private-device',dcGroupCode:'JAWS',authToken:{accessToken:'owner-token',refreshToken:'refresh-secret'}};
 const context={Response,Request,URL,URLSearchParams,AbortSignal,TransformStream,btoa,Uint8Array,
  Deno:{env:{get:name=>({SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'server-secret'})[name]},serve:handler=>serve=handler},
  fetch:async(url,options)=>{
   calls.push({url,options});
   if(url.endsWith('/auth/v1/user'))return Response.json({id:'member',email_confirmed_at:'confirmed'},{status:mode==='expired'?401:200});
   if(url.includes('/rpc/sakura_library_jio_read'))return Response.json({provider:'jio',session,accounts:{account2:{provider:'jio',session:{...session,userId:'second-owner'}}}});
   if(url.includes('/rpc/sakura_library_jio_write')){assert.equal(JSON.parse(options.body).payload.session.authToken.accessToken,'new-token');return Response.json(null);}
   if(url.includes('/rest/v1/sakura_model_catalogue'))return Response.json(url.includes('&id=')?
     [{jio_object_key:mode==='invalid-object'?'https://attacker.example/key':mode==='secondary'?'account2__private-object':'private-object',jio_preview_object_key:'private-preview',bytes:4}]:
     [{id:'model',format:'live2d',bytes:4,jio_preview_object_key:'private-preview'}]);
   if(url.endsWith('/assets/runtime-config.json'))return Response.json({envHeaders:{'X-Api-Key':'public-web-key','X-App-Secret':'public-web-secret'}});
   if(url==='https://api.jioaicloud.com/account/token/refresh'){refreshes++;return Response.json({accessToken:'new-token',refreshToken:'rotated-refresh'});}
   if(url.startsWith('https://jaws-dl.jioaicloud.com/download/files/')){
    assert.equal(options.headers['Accept-Language'],'en');assert.equal(options.redirect,'error');
    assert.equal(options.headers['X-User-Id'],mode==='secondary'?'second-owner':'private-owner');
    if(expired){expired=false;return Response.json({},{status:401});}
    return new Response(new Uint8Array(mode==='oversized'?[1,2,3,4,5]:[1,2,3,4]));
   }
   throw Error('Unexpected request '+url);
  }};
 vm.runInNewContext(fs.readFileSync('tools/model-library-jio-edge.js','utf8')+'\n'+fs.readFileSync('tools/model-library-edge.js','utf8'),context);
 const base='https://project.supabase.co/functions/v1/sakura-library',headers={Authorization:'Bearer sakura-member'};
 let r=await serve(new Request(base+'/v1/models'));assert.equal(r.status,401);assert.equal(calls.length,0);
 mode='expired';r=await serve(new Request(base+'/v1/models/model/package',{headers}));assert.equal(r.status,401);assert.equal(calls.some(c=>c.url.includes('jioaicloud')),false);
 mode='valid';r=await serve(new Request(base+'/v1/models',{headers}));const listing=await r.json();assert.equal(listing.models[0].preview,true);assert.equal(JSON.stringify(listing).includes('private-'),false);
 r=await serve(new Request(base+'/v1/models/model/package',{headers}));assert.equal(r.status,200);assert.equal((await r.arrayBuffer()).byteLength,4);
 assert.equal([...r.headers.values()].join().includes('owner-token'),false);
 expired=true;r=await serve(new Request(base+'/v1/models/model/package',{headers}));assert.equal((await r.arrayBuffer()).byteLength,4);assert.equal(refreshes,1);
 mode='secondary';r=await serve(new Request(base+'/v1/models/model/package',{headers}));assert.equal(r.status,200);assert.equal((await r.arrayBuffer()).byteLength,4);
 mode='invalid-object';let before=calls.filter(c=>c.url.includes('jioaicloud')).length;r=await serve(new Request(base+'/v1/models/model/package',{headers}));assert.equal(r.status,503);assert.equal(calls.filter(c=>c.url.includes('jioaicloud')).length,before);
 mode='oversized';r=await serve(new Request(base+'/v1/models/model/package',{headers}));await assert.rejects(()=>r.arrayBuffer());
 console.log('PASS: Jio private streaming, Sakura auth, safe catalogue, host allowlist, language header, refresh and size limits.');
})().catch(e=>{console.error(e);process.exitCode=1;});
