const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(String(error)));
  page.on('console',message=>{if(message.type()==='error'&&/shader|VALIDATE_STATUS/i.test(message.text()))errors.push(message.text());});
  await page.route('http://toon.test/**',route=>{
   const relative=decodeURIComponent(new URL(route.request().url()).pathname).slice(1);
   if(!relative)return route.fulfill({contentType:'text/html',body:'<script type="importmap">{"imports":{"three":"/static/vendor/three/build/three.module.js"}}</script>'});
   const file=path.resolve(relative);
   if(!file.startsWith(path.resolve('static')+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
   return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(file)});
  });
  await page.goto('http://toon.test/');
  const pixels=await page.evaluate(async()=>{
   const T=await import('three');
   const {MMDToonShader}=await import('/static/vendor/three/examples/jsm/shaders/MMDToonShader.js');
   const {applyPmxReferenceLighting}=await import('/static/js/pmx-reference-lighting.js');
   const renderer=new T.WebGLRenderer({antialias:false,preserveDrawingBuffer:true});renderer.setSize(16,16);
   renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.NoToneMapping;
   const scene=new T.Scene(),camera=new T.OrthographicCamera(-1,1,1,-1,.1,10);camera.position.z=2;
   const light=new T.DirectionalLight(0xffffff,1);light.position.set(0,0,1);scene.add(light);
   const texture=values=>{const t=new T.DataTexture(new Uint8Array(values),1,1,T.RGBAFormat);t.colorSpace=T.SRGBColorSpace;t.needsUpdate=true;return t;};
   const geometry=new T.PlaneGeometry(2,2),mesh=new T.Mesh(geometry);scene.add(mesh);
   const result={};
   for(const [name,ramp,ambient,controls] of [['coloured',[64,128,192,255],[.5,.5,.5]],['white',[255,255,255,255],[.5,.5,.5]],['absent',null,[.5,.5,.5]],['ambient',[64,128,192,255],[.1,.1,.1]],['shine',[255,255,255,255],[.5,.5,.5]],['multiply',[255,255,255,255],[.5,.5,.5]],['dark',[255,255,255,255],[0,0,0]],['side',[255,255,255,255],[.5,.5,.5]],['pastel',[255,255,255,255],[.6,.6,.6]],['dim',[255,255,255,255],[.5,.5,.5],{brightness:.5}],['desaturated',[64,128,192,255],[.5,.5,.5],{saturation:0}],['noToon',[64,128,192,255],[.5,.5,.5],{toon:0}],['noFill',[255,255,255,255],[.5,.5,.5],{ambient:0}],['normalLight',[255,255,255,255],[0,0,0],{normal:1}],['noSphere',[255,255,255,255],[.5,.5,.5],{sphere:0}],['noTint',[255,255,255,255],[.5,.5,.5],{diffuse:0}],['sphereToon',[128,128,128,255],[.5,.5,.5]]]){
    // The loader's MMDToonMaterial is private. Expose its shader uniforms using
    // the same public Three.js ShaderMaterial API, with a controlled flat plane.
    const material=new T.ShaderMaterial({uniforms:T.UniformsUtils.clone(MMDToonShader.uniforms),vertexShader:MMDToonShader.vertexShader,fragmentShader:MMDToonShader.fragmentShader,defines:{...MMDToonShader.defines},lights:true});
    material.isMMDToonMaterial=true;
    for(const key of ['map','gradientMap','diffuse','specular','matcap'])Object.defineProperty(material,key,{get(){return this.uniforms[key].value;},set(value){this.uniforms[key].value=value;}});
    material.map=texture([255,255,255,255]);material.gradientMap=ramp?texture(ramp):null;material.specular.setRGB(0,0,0);
    if(['shine','multiply','noSphere','sphereToon'].includes(name)){material.map.dispose();material.map=texture([64,64,64,255]);material.matcap=texture([32,64,96,255]);}
    if(name==='multiply'){delete material.defines.MATCAP_BLENDING_ADD;material.defines.MATCAP_BLENDING_MULTIPLY=true;}
    light.position.set(name==='side'?1:0,0,name==='side'?0:1);
    material.userData.MMD={};applyPmxReferenceLighting(material,{diffuse:name==='pastel'?[.8,.8,.8,1]:name==='noTint'?[.2,.2,.2,1]:[1,1,1,1],ambient});for(const [key,value]of Object.entries(controls||{}))material.uniforms['sakuraPmxControl_'+key].value=value;mesh.material=material;
    renderer.render(scene,camera);const gl=renderer.getContext(),px=new Uint8Array(4);gl.readPixels(8,8,1,1,gl.RGBA,gl.UNSIGNED_BYTE,px);result[name]=Array.from(px);
    material.map.dispose();material.matcap?.dispose();if(ramp)material.gradientMap.dispose();material.dispose();
   }
   geometry.dispose();renderer.dispose();return result;
  });
  for(const [name,expected] of Object.entries({coloured:[64,128,192],white:[255,255,255],absent:[255,255,255],ambient:[45,90,134],shine:[96,128,160],multiply:[8,16,24],dark:[0,0,0],side:[255,255,255],pastel:[255,255,255],dim:[128,128,128],desaturated:[119,119,119],noToon:[255,255,255],noFill:[0,0,0],normalLight:[255,255,255],noSphere:[64,64,64],noTint:[255,255,255],sphereToon:[48,64,80]})){
   assert.ok(pixels[name].slice(0,3).every((value,index)=>Math.abs(value-expected[index])<=2),`${name}: ${pixels[name]} expected ${expected}`);
  }
  assert.deepEqual(errors,[]);console.log('PASS: real WebGL preserves RGB toon colour, raw ambient addition and white defaults',JSON.stringify(pixels));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
