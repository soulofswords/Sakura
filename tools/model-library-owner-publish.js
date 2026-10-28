const expected="__OWNER_TOKEN_SHA256__";
Deno.serve(async request=>{
try{
 if(request.method!=="POST")return new Response("Unavailable",{status:410});
 const token=(request.headers.get("Authorization")||"").replace(/^Bearer /,"");
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(token)))).map(x=>x.toString(16).padStart(2,"0")).join("");
 if(digest!==expected)return new Response("Unauthorized",{status:401});
 const raw=await request.text();if(raw.length>16000)return new Response("Too large",{status:413});const entry=JSON.parse(raw);
 if(!/^live2d-[a-f0-9]{24}$/.test(entry.id)||entry.format!=="live2d"||!Number.isSafeInteger(entry.bytes)||entry.bytes<1||entry.bytes>536870912||!/^[a-f0-9]{64}$/.test(entry.sha256)||typeof entry.name!=="string"||entry.name.length>200||!/^[A-Za-z0-9_-]{1,200}$/.test(entry.drive_file_id))return new Response("Invalid model record",{status:400});
 if(entry.preview_drive_file_id&&!/^[A-Za-z0-9_-]{1,200}$/.test(entry.preview_drive_file_id))return new Response("Invalid preview",{status:400});
 const row=Object.fromEntries(["id","name","format","bytes","sha256","version","mobile_compatible","drive_file_id","preview_drive_file_id"].map(k=>[k,entry[k]??null]));row.published=true;
 const project=Deno.env.get("SUPABASE_URL"),admin=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
 const answer=await fetch(project+"/rest/v1/sakura_model_catalogue?on_conflict=id",{method:"POST",headers:{apikey:admin,Authorization:"Bearer "+admin,"Content-Type":"application/json",Prefer:"resolution=merge-duplicates"},body:JSON.stringify(row),redirect:"error"});
 return new Response(answer.ok?"Published":"Publication failed",{status:answer.ok?200:503,headers:{"Cache-Control":"no-store"}});
}catch(_){return new Response("Publication failed",{status:503});}
});
