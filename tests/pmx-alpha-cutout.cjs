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


 const result=await page.evaluate(async()=>{
  const THREE=await import('three'),{MMDLoader}=await import('/static/vendor/three/examples/jsm/loaders/MMDLoader.js?v=cutout-uniform2');
  const loader=new MMDLoader(),geometry=new THREE.PlaneGeometry(2,2);
  const data={metadata:{format:'pmx',materialCount:1},materials:[{name:'cutout',diffuse:[1,1,1,1],specular:[0,0,0],ambient:[1,1,1],shininess:1,flag:1,textureIndex:-1,envTextureIndex:-1,toonIndex:-1,toonFlag:1,edgeSize:0,edgeColor:[0,0,0,0]}],morphs:[]};
  const material=loader.meshBuilder.materialBuilder.build(data,geometry)[0];
  const map=new THREE.DataTexture(new Uint8Array([255,255,255,0]),1,1);map.needsUpdate=true;map.generateMipmaps=false;
  material.map=map;material.transparent=true;material.depthWrite=true;material.alphaTest=.01;material.blending=THREE.NormalBlending;material.needsUpdate=true;
  const renderer=new THREE.WebGLRenderer({alpha:true}),scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=2;
  scene.add(new THREE.AmbientLight(0xffffff,1));
  const front=new THREE.Mesh(geometry,material);front.position.z=.2;front.renderOrder=0;scene.add(front);
  const back=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({color:0x00ff00,transparent:true,opacity:1}));back.renderOrder=1;scene.add(back);
  const target=new THREE.WebGLRenderTarget(16,16);renderer.setRenderTarget(target);renderer.setClearColor(0,1);
  const pixel=()=>{renderer.clear();renderer.render(scene,camera);const p=new Uint8Array(4);renderer.readRenderTargetPixels(target,8,8,1,1,p);return Array.from(p);};
  const cutout=pixel(),cutoff=material.uniforms.alphaTest.value;
  material.alphaTest=0;const zero=pixel(),zeroUniform=material.uniforms.alphaTest.value;
  const clone=material.clone();clone.alphaTest=.1;front.material=clone;const cloned=pixel(),cloneUniform=clone.uniforms.alphaTest.value;
  target.dispose();geometry.dispose();map.dispose();material.dispose();clone.dispose();back.material.dispose();renderer.dispose();
  return {cutout,cutoff,zero,zeroUniform,cloned,cloneUniform};
 });
 assert.deepEqual(result.cutout,[0,255,0,255]);assert.equal(result.cutoff,.01);
 assert.deepEqual(result.zero,[0,0,0,255]);assert.equal(result.zeroUniform,0);
 assert.deepEqual(result.cloned,[0,255,0,255]);assert.equal(result.cloneUniform,.1);
 assert.deepEqual(shaderErrors,[]);
 console.log('PASS: PMX cutout fragments stop writing invisible depth, including changed thresholds, zero reset and cloned materials',JSON.stringify(result));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
