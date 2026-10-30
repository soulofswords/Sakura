const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:700,height:850}}),shaderErrors=[];
  let brokenTextures=false;
  page.on('console',message=>{if(message.type()==='error'&&/Shader Error|VALIDATE_STATUS|shader error/i.test(message.text()))shaderErrors.push(message.text());});
  await page.route('http://pmx.test/**',route=>{
   const url=new URL(route.request().url()),relative=decodeURIComponent(url.pathname).slice(1),file=path.resolve(relative);
   if(!file.startsWith(process.cwd()+path.sep)||!['static','models'].includes(relative.split('/')[0]))return route.fulfill({status:404,body:''});
   // Simulate unreadable artwork; do not depend on corrupt owner files remaining
   // corrupt after they have been recovered from their intact originals.
   if(brokenTextures&&/Gratia_MMD\/tex\/T_GratiaDefault_(Face01|Skin01|Hair01|Hat01|Pupil01|EyeTrans01|Special01)_A_D\.png$/i.test(relative))return route.fulfill({contentType:'image/png',body:Buffer.alloc(32)});
   if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':'application/octet-stream',body:fs.readFileSync(file)});
   if(relative.startsWith('models/')&&/\.(png|bmp|tga|dds|sph|spa)$/i.test(relative)){
    const color=url.searchParams.get('fallback')==='black'?'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAX+XDSwAAAABJRU5ErkJggg==':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==';
    return route.fulfill({contentType:'image/png',body:Buffer.from(color,'base64')});
   }
   return route.fulfill({status:404,body:''});
  });
  await page.goto('http://pmx.test/static/library-audit.html?no-capture');await page.waitForFunction(()=>window.auditReady);

  const rotated=await page.evaluate(async()=>{
   const source=await (await fetch('/static/vendor/three/examples/jsm/loaders/MMDLoader.js')).text();
   const body=source.match(/_getRotatedImage\( image \) \{([\s\S]*?)\n\t\}/)[1];const rotate=new Function('image',body);
   const rows=[];for(const [w,h]of [[16,250],[250,16],[32,32]]){
    const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');ctx.fillStyle='#abcdef';ctx.fillRect(0,0,w,h);
    const image=rotate(canvas);let transparent=0;for(let i=3;i<image.data.length;i+=4)if(image.data[i]<255)transparent++;
    rows.push({w:image.width,h:image.height,transparent});
   }return rows;
  });
  assert.deepEqual(rotated,[{w:250,h:16,transparent:0},{w:16,h:250,transparent:0},{w:32,h:32,transparent:0}]);
  const actual=await page.evaluate(async()=>{
   const result=await auditModel('pmx/Touhou/Ran & Yukari Yakumo/Ran Yakumo (One Piece) v2.0/Ran Yakumo (One Piece) v2.0.pmx');
   const v=auditViewer,materials=v.model.material;const original=materials.map(m=>m.visible);
   function sample(name){materials.forEach(m=>m.visible=m.name===name);const frame=v.captureTextureDiagnosticFrame(960);let n=0,total=0;for(let i=0;i<frame.pixels.length;i+=4)if(frame.pixels[i+3]>240){n++;total+=frame.pixels[i]+frame.pixels[i+1]+frame.pixels[i+2];}const m=materials.find(m=>m.name===name);return {name,n,mean:total/Math.max(1,n*3),size:[m.gradientMap.image.width,m.gradientMap.image.height]};}
   const samples=[sample('Hair Tails'),sample('Hat2')];materials.forEach((m,i)=>m.visible=original[i]);
   return {ok:result.ok,samples};
  });
  assert.equal(actual.ok,true);for(const sample of actual.samples){assert.deepEqual(sample.size,[250,16]);assert.ok(sample.n>100);assert.ok(sample.mean>80,JSON.stringify(sample));}
  assert.deepEqual(shaderErrors,[]);console.log('PASS: non-square toon rotation preserves all pixels and restores Ran hair/hat in real WebGL',JSON.stringify(actual));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
