const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage();
  await page.route('http://sakura.test/**',route=>{
   const name=new URL(route.request().url()).pathname;
   if(name==='/')return route.fulfill({contentType:'text/html',body:'<script type="importmap">{"imports":{"three":"/static/vendor/three/build/three.module.js","three/addons/":"/static/vendor/three/examples/jsm/"}}</script>'});
   return route.fulfill({contentType:'text/javascript',body:fs.readFileSync(path.join(process.cwd(),name))});
  });
  await page.goto('http://sakura.test/');
  const result=await page.evaluate(async()=>{
   const {decodeReplacementImage,ModelMaterials}=await import('/static/js/model-materials.js');
   const THREE=await import('three');
   const canvas=document.createElement('canvas');canvas.width=canvas.height=2;canvas.getContext('2d').fillRect(0,0,2,2);
   const png=await new Promise(r=>canvas.toBlob(r,'image/png'));
   const mislabeled=await decodeReplacementImage(new File([png],'texture.tga',{type:'image/tga'}));
   const webp=await new Promise(r=>canvas.toBlob(r,'image/webp'));
   const decodedWebp=await decodeReplacementImage(webp);
   const bytes=new Uint8Array(18+12);bytes[2]=2;bytes[12]=bytes[14]=2;bytes[16]=24;
   for(let i=18;i<bytes.length;i+=3){bytes[i]=190;bytes[i+1]=180;bytes[i+2]=250;}
   const tga=await decodeReplacementImage(new Blob([bytes]));
   const material=new THREE.MeshBasicMaterial({color:0xffffff});
   const editor=new ModelMaterials({});editor.entries=[{id:'mat:0',kind:'material',material,base:{map:null,color:material.color.clone(),opacity:1,transparent:false,depthWrite:true,alphaTest:0}}];
   await editor.setRemap('mat:0',new Blob([bytes]));
   const compressed=new THREE.CompressedTexture([{data:new Uint8Array(8),width:4,height:4}],4,4,THREE.RGB_S3TC_DXT1_Format);
   compressed.colorSpace=THREE.SRGBColorSpace;compressed.flipY=false;
   editor.entries[0].base.map=compressed;
   await editor.setRemap('mat:0',new Blob([bytes]));
   const ddsReplaced=!material.map.isCompressedTexture&&material.map.format===THREE.RGBAFormat&&material.map.mipmaps.length===0&&material.map.flipY===false;
   let junk=false,oversize=false;
   try{await decodeReplacementImage(new Blob([new Uint8Array(16)]));}catch{junk=true;}
   const huge=new Uint8Array(18);huge[2]=2;huge[12]=huge[13]=huge[14]=huge[15]=255;
   try{await decodeReplacementImage(new Blob([huge]));}catch{oversize=true;}
   return {png:mislabeled.width,webp:decodedWebp.width,tga:tga.width,pixel:[...tga.source.getContext('2d').getImageData(0,0,1,1).data],applied:material.map?.image?.width,space:material.map?.colorSpace,junk,oversize,ddsReplaced};
  });
  assert.deepEqual(result,{png:2,webp:2,tga:2,pixel:[250,180,190,255],applied:2,space:'srgb',junk:true,oversize:true,ddsReplaced:true});
  console.log('PASS: real browser TGA/PNG/WebP decoding, mislabeled PNG, material replacement, sRGB and bounded invalid headers');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
