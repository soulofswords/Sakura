const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('static/js/model-viewer.js','utf8');
const loader=source.slice(source.indexOf('class SmartTgaLoader'),source.indexOf('export default class ModelViewer'));
let payload,ddsParses=0;
const tracked=[];
class Texture {constructor(){this.mipmaps=[];}}
class CompressedTexture extends Texture {constructor(mipmaps,width,height){super();this.mipmaps=mipmaps;this.image={width,height};this.isCompressedTexture=true;}}
const manager={resolveURL:x=>x,itemStart:x=>tracked.push(['start',x]),itemEnd:x=>tracked.push(['end',x]),itemError:x=>tracked.push(['error',x])};
const context={
    THREE:{Texture,CompressedTexture,LinearFilter:1006,Loader:class{constructor(m){this.manager=m;}},FileLoader:class{setResponseType(){}load(u,fn){fn(payload);}}},
    TGALoader:class{parse(){throw Error('PNG fallback must not use TGA decoder');}},
    DDSLoader:class{parse(){ddsParses++;return {width:4,height:4,mipmaps:[{data:new Uint8Array(8),width:4,height:4}],format:33776};}},
    Blob,URL:{createObjectURL:()=> 'blob:decoded',revokeObjectURL(){}},
    Image:class{set src(value){queueMicrotask(()=>{this.width=1;this.height=1;this.onload();});}},
    console,queueMicrotask,
};
vm.runInNewContext(loader+'\nthis.Loader=SmartTgaLoader;',context);
(async()=>{
    payload=new Uint8Array([137,80,78,71,13,10,26,10]).buffer;
    let loaded;
    const image=new context.Loader(manager).load('missing.dds',texture=>loaded=texture);
    assert.equal(tracked[0][0],'start','Image decoding tracked before async callback');
    assert.equal(loaded,undefined);
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(loaded,image);
    assert.equal(image.isCompressedTexture,false);
    assert.ok(Array.isArray(image.mipmaps));
    assert.equal(tracked.at(-1)[0],'end');
    assert.equal(ddsParses,0,'DDS filename with PNG data uses image decoder');
    payload=new Uint8Array([68,68,83,32,0,0,0,0]).buffer;
    const compressed=new context.Loader(manager).load('real.dds',()=>{});
    assert.equal(ddsParses,1);
    assert.equal(compressed.isCompressedTexture,true);
    assert.equal(compressed.image.width,4);
    console.log('PASS: missing DDS PNG fallback waits for decoding; real DDS uses compressed texture');
})().catch(error=>{console.error(error);process.exitCode=1});
