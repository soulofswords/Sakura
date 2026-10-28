const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
(async()=>{
 let serve, mode='valid',seen=[];
 const context={Response,Request,URL,URLSearchParams,AbortSignal,TransformStream,
  Deno:{env:{get:name=>({SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'server-secret'})[name]},serve:handler=>serve=handler},
  fetch:async(url,options)=>{
   seen.push({url,options});
   if(url.endsWith('/auth/v1/user'))return Response.json(mode==='unconfirmed'?{id:'member'}:{id:'member',email_confirmed_at:'2026-10-25'},{status:mode==='expired'?401:200});
   if(mode==='large'&&url.includes('/rest/v1/')&&!url.includes('&id=')){const offset=Number(new URL(url).searchParams.get('offset'));return Response.json(Array.from({length:Math.min(500,1256-offset)},(_,i)=>({id:'model-'+(offset+i),format:'pmx',jio_preview_object_key:'private-preview'})));}
   if(url.includes('/rest/v1/'))return Response.json(url.includes('&id=')?
    (url.includes('id=eq.character')?[{preview_storage_path:'previews/character.webp'}]:[]):
    [{id:'character',format:'live2d',preview_storage_path:'previews/character.webp',preview_drive_file_id:'private-file-id'}]);
   if(url.includes('/storage/v1/object/previews/character.webp'))return new Response(new Uint8Array([82,73,70,70,0,0,0,0,87,69,66,80]));
   throw new Error('Unexpected external request');
  }};
 vm.runInNewContext(fs.readFileSync('tools/model-library-edge.js','utf8'),context);
 const base='https://project.supabase.co/functions/v1/sakura-library';
 let response=await serve(new Request(base+'/v1/models'));
 assert.equal(response.status,401);assert.equal(seen.length,0);
 const headers={Authorization:'Bearer user-session'};
 mode='expired';response=await serve(new Request(base+'/v1/models',{headers}));assert.equal(response.status,401);
 mode='unconfirmed';response=await serve(new Request(base+'/v1/models',{headers}));assert.equal(response.status,403);
 mode='valid';response=await serve(new Request(base+'/v1/models',{headers}));assert.equal(response.status,200);
 const entry=(await response.json()).models[0];
 assert.equal(entry.id,'character');assert.equal(entry.preview,true);
 assert.equal(entry.preview_storage_path,undefined);assert.equal(entry.preview_drive_file_id,undefined);
 assert.equal(response.headers.get('Cache-Control'),'private, no-store');
 assert.ok(seen.at(-1).url.includes('published=eq.true'));
 assert.ok(!JSON.stringify(entry).includes('private-file-id'));
 mode='large';response=await serve(new Request(base+'/v1/models',{headers}));const catalogue=(await response.json()).models;assert.equal(catalogue.length,1256);assert.equal(new Set(catalogue.map(x=>x.id)).size,1256);assert.ok(catalogue.every(x=>x.preview&&!('jio_preview_object_key' in x)));mode='valid';
 response=await serve(new Request(base+'/v1/models/character/preview',{headers}));
 assert.equal(response.status,200);assert.equal(response.headers.get('Content-Type'),'image/webp');
 assert.equal((await response.arrayBuffer()).byteLength,12);
 response=await serve(new Request(base+'/v1/models/unlisted/package',{headers}));assert.equal(response.status,404);
 console.log('PASS: hosted function rejects anonymous, expired and unconfirmed accounts; returns only published catalogue metadata.');
})().catch(error=>{console.error(error);process.exitCode=1;});
