// Optional owner-PC check with real installed characters; no files are modified.
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),http=require('http'),assert=require('node:assert/strict');
(async()=>{
 const source=process.cwd(),models=path.resolve(process.argv[2]||'../Sakura Companion/Sakura/models');
 const characters=[['pmx','AI_Assistant_PMX_Models/Helen_Repair_2026_10_25/Helen.pmx','Helen'],['vrm','1439626354518702295.vrm','Anna']];
 const server=http.createServer((req,res)=>{
  const location=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(location==='/test.html'){
   res.setHeader('Content-Type','text/html');res.end(`<!doctype html>${characters.map(([format,file,name])=>`<div id="${format==='pmx'?'model':format}-dropdown"><button class="dropdown-trigger">${format.toUpperCase()}</button><select hidden id="${format==='pmx'?'model':format}-select"><option value="${format}/${file}">${name}</option></select></div>`).join('')}<script type="module" src="/static/js/local-character-library.js"></script>`);return;
  }
  const root=location.startsWith('/models/')?models:location.startsWith('/static/')?path.join(source,'static'):null;
  const relative=location.replace(/^\/(models|static)\//,'');const target=root&&path.resolve(root,relative);
  if(!root||!target.startsWith(root+path.sep)||!fs.existsSync(target)||!fs.statSync(target).isFile()){res.writeHead(404);res.end();return;}
  const types={'.html':'text/html','.js':'application/javascript','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'};
  res.setHeader('Content-Type',types[path.extname(target)]||'application/octet-stream');fs.createReadStream(target).pipe(res);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:850}});
  await page.goto('http://127.0.0.1:'+server.address().port+'/test.html');
  for(const [format,,name] of characters){
   await page.getByRole('button',{name:format.toUpperCase(),exact:true}).click();
   const dialog=page.locator('#local-character-library');await dialog.getByRole('searchbox').fill(name);
   await dialog.locator('.local-character-square img').waitFor({timeout:60000});
   const card=dialog.getByRole('button',{name:format.toUpperCase()+' · '+name,exact:true});await card.hover();
   const frame=page.frames().find(frame=>frame.url().includes('model-library-preview.html'));
   assert.ok(frame);await frame.waitForFunction(()=>{const iframe=parent.document.querySelector('iframe');return parseFloat(iframe.style.left)>0;});
   const first=await frame.locator('canvas').screenshot();await page.waitForTimeout(350);const next=await frame.locator('canvas').screenshot();
   assert.notDeepEqual(first,next,'The 3D preview must rotate.');
   await dialog.getByRole('button',{name:'Close character library'}).click();
  }
  console.log('PASS: real PMX and VRM thumbnails render, hover rotates without reloading the iframe.');
 }finally{await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
