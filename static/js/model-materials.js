import * as THREE from 'three';
import { TGALoader } from 'three/addons/loaders/TGALoader.js';

// Chromium cannot decode TGA, and rigs label PNG/JPG/BMP artwork with a .tga
// suffix constantly, so the decoder is chosen from the bytes, never the name.
function signatureOf(buffer) {
    const b = new Uint8Array(buffer, 0, Math.min(buffer.byteLength, 12));
    return {
        png: b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4E && b[3] === 0x47,
        jpeg: b[0] === 0xFF && b[1] === 0xD8,
        bmp: b[0] === 0x42 && b[1] === 0x4D,
        gif: b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46,
        webp: b[0] === 0x52 && b[1] === 0x49 && b[2] === 0x46 && b[3] === 0x46 && b[8] === 0x57 && b[9] === 0x45 && b[10] === 0x42 && b[11] === 0x50,
    };
}

function tgaToCanvas(buffer) {
    if(buffer.byteLength<18)throw Error('The TGA header is incomplete.');
    const header=new DataView(buffer),width=header.getUint16(12,true),height=header.getUint16(14,true);
    if(![1,2,3,9,10,11].includes(header.getUint8(2))||!width||!height||width*height>16777216)
        throw Error('Use a valid TGA image up to 4096 × 4096 pixels.');
    const parsed = new TGALoader().parse(buffer);
    if (!parsed.width || !parsed.height || parsed.data?.length !== parsed.width * parsed.height * 4) {
        throw Error('The TGA image is incomplete.');
    }
    const canvas = document.createElement('canvas');
    canvas.width = parsed.width; canvas.height = parsed.height;
    canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(parsed.data), parsed.width, parsed.height), 0, 0);
    return canvas;
}

export async function decodeReplacementImage(blob) {
    const buffer = await blob.arrayBuffer();
    const mark = signatureOf(buffer);
    let source;
    if (mark.png || mark.jpeg || mark.bmp || mark.gif || mark.webp) {
        const url = URL.createObjectURL(blob);
        try {
            source = await new Promise((resolve, reject) => {
                const image = new Image();
                image.onload = () => resolve(image);
                image.onerror = () => reject(Error('The image could not be decoded.'));
                image.src = url;
            });
        } finally { URL.revokeObjectURL(url); }
    } else source = tgaToCanvas(buffer);
    return { source, width: source.naturalWidth || source.width, height: source.naturalHeight || source.height };
}

// Reversible overrides: source files, texture alpha and UV layouts stay intact.
export class ModelMaterials {
    constructor(viewer) { this.viewer=viewer;this.entries=[];this.replacements=new Map();this.colors={}; }
    attach(key) {
        this.restore();this.key=key;this.entries=[];
        const live=this.viewer.live2d;
        if(live) {
            const core=live.avatar.internalModel.coreModel,renderer=live.avatar.internalModel.renderer;
            this.live=live;this.core=core;this.renderer=renderer;
            core.getDrawableIds().forEach((name,i)=>this.entries.push({id:`art:${i}`,name:String(name),index:i,kind:'art'}));
            this.drawOriginal=renderer.drawMesh;
            const indices=new Map(this.entries.map(e=>[core.getDrawableVertexIndices(e.index),e.id]));
            const owner=this;
            renderer.drawMesh=function(...args) {
                const id=indices.get(args[3]),settings=owner.colors[id],base=this.getModelColor();
                const mask=this.getClippingContextBufferForMask?.();
                if(settings&&!mask) {
                    const c=new THREE.Color(settings.color),f=settings.strength;
                    // Cubism's shader accepts colors in its existing texture space.
                    const opacity=settings.opacity??1;
                    // Strengthen drawable opacity while keeping atlas cutouts
                    // and clipping masks intact.
                    if(opacity>1&&Number.isFinite(args[6])&&args[6]>0)args[6]+=(1-args[6])*(opacity-1);
                    c.convertLinearToSRGB();this.setModelColor(base.R*(1-f+f*c.r),base.G*(1-f+f*c.g),base.B*(1-f+f*c.b),base.A*Math.min(1,opacity));
                }
                if(owner.hoverId===id&&!mask)this.setModelColor(.3,1,1,base.A);
                try{return owner.drawOriginal.apply(this,args);}finally{this.setModelColor(base.R,base.G,base.B,base.A);}
            };
            live.avatar.textures.forEach((texture,i)=>this.entries.push({id:`atlas:${i}`,name:`Texture atlas ${i+1}`,index:i,kind:'atlas',base:texture}));
        } else {
            this.live=null;const seen=new Set();
            this.viewer.model?.traverse(mesh=>{
                for(const material of (Array.isArray(mesh.material)?mesh.material:[mesh.material])) {
                    if(!material||seen.has(material)||!material.color)continue;seen.add(material);
                    this.entries.push({id:`mat:${this.entries.length}`,name:material.name||`Material ${this.entries.length+1}`,kind:'material',material,
                        base:{map:material.map,color:material.color.clone(),opacity:material.opacity,transparent:material.transparent,depthWrite:material.depthWrite,alphaTest:material.alphaTest,pmxDiffuse:material.uniforms?.sakuraPmxDiffuse?.value.clone(),pmxAmbient:material.uniforms?.sakuraPmxAmbient?.value.clone()}});
                }
            });
        }
        return this.entries;
    }
    colorTargets(){return this.entries.filter(e=>e.kind!=='atlas');}
    remapTargets(){return this.entries.filter(e=>e.kind!=='art');}
    entry(id){return this.entries.find(e=>e.id===id);}
    setColor(id,settings) {
        const e=this.entry(id);if(!e)throw Error('Choose a model part.');
        const previous=this.colors[id];
        if(settings&&!/^#[0-9a-f]{6}$/i.test(settings.color))throw Error('Choose a valid color.');
        if(settings)this.colors[id]={color:settings.color,strength:Math.max(0,Math.min(1,Number(settings.strength)||0)),opacity:Math.max(0,Math.min(2,Number.isFinite(Number(settings.opacity))?Number(settings.opacity):1))};else delete this.colors[id];
        if(e.kind==='art')return;
        try{this.applyMaterial(e);}catch(error){if(previous)this.colors[id]=previous;else delete this.colors[id];throw error;}
    }
    applyMaterial(e) {
        const source=this.replacements.get(e.id)||e.base.map,setting=this.colors[e.id];
        const previous=e.generated;e.generated=null;
        e.material.color.copy(e.base.color);
        // The shared PMX shader reads authored uniforms, not material.color.
        // Restore first so transparency-only edits and reset keep authored lighting.
        const pmxDiffuse=e.material.uniforms?.sakuraPmxDiffuse?.value;
        const pmxAmbient=e.material.uniforms?.sakuraPmxAmbient?.value;
        if(e.base.pmxDiffuse)pmxDiffuse?.copy(e.base.pmxDiffuse);
        if(e.base.pmxAmbient)pmxAmbient?.copy(e.base.pmxAmbient);
        const opacity=setting?.opacity??1;
        e.material.opacity=opacity>1?e.base.opacity+(1-e.base.opacity)*(opacity-1):e.base.opacity*opacity;
        const forceOpaque=opacity>1&&e.material.opacity>=.999;
        e.material.transparent=forceOpaque?false:(e.base.transparent||e.material.opacity<.999);
        e.material.depthWrite=forceOpaque?true:(e.material.opacity<.999?false:e.base.depthWrite);
        e.material.alphaTest=forceOpaque&&e.base.map?.transparent===true
            ?Math.max(e.base.alphaTest||0,.01):(e.base.alphaTest||0);
        try {
            if(!setting||(setting.strength===0&&opacity<=1)){e.material.map=source;return;}
            const target=new THREE.Color(setting.color).convertLinearToSRGB();
            if(!source){
                e.material.color.lerp(new THREE.Color(setting.color),setting.strength);
                if(e.base.pmxDiffuse)pmxDiffuse.lerp(new THREE.Vector3(target.r,target.g,target.b),setting.strength);
                if(e.base.pmxAmbient)pmxAmbient.lerp(new THREE.Vector3(.5,.5,.5),setting.strength);
                return;
            }
            if(source.isCompressedTexture)throw Error('Recoloring this compressed texture needs a PNG/JPG replacement first.');
            const image=source.image,w=image?.naturalWidth||image?.width,h=image?.naturalHeight||image?.height;
            if(!w||!h)throw Error('The texture image is not ready.');
            if(w*h>16777216)throw Error('Use a replacement image up to 4096 × 4096 for coloring.');
            const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
            const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0);
            const pixels=context.getImageData(0,0,w,h),d=pixels.data;
            // Normalize average brightness so dark/blue textures can become a
            // new color rather than turning black when RGB is multiplied.
            let sum=0,count=0;
            for(let i=0;i<d.length;i+=4)if(d[i+3]>0){sum+=(.2126*d[i]+.7152*d[i+1]+.0722*d[i+2])/255;count++;}
            const reference=Math.max(.12,sum/Math.max(1,count));
            const channels=[target.r,target.g,target.b];
            for(let i=0;i<d.length;i+=4)if(d[i+3]>0){
                if(opacity>1)d[i+3]=Math.min(255,Math.round(d[i+3]*opacity));
                const light=(.2126*d[i]+.7152*d[i+1]+.0722*d[i+2])/255/reference;
                for(let c=0;c<3;c++)d[i+c]=Math.round(d[i+c]*(1-setting.strength)+Math.min(255,255*channels[c]*light)*setting.strength);
            }
            context.putImageData(pixels,0,0);
            const map=source.clone();map.source=new THREE.Source(canvas);map.needsUpdate=true;
            // Authored diffuse tints must not multiply a newly selected hue
            // back into darkness. Restore the original tint on reset.
            e.material.color.lerp(new THREE.Color(0xffffff),setting.strength);
            if(e.base.pmxDiffuse)pmxDiffuse.lerp(new THREE.Vector3(1,1,1),setting.strength);
            if(e.base.pmxAmbient)pmxAmbient.lerp(new THREE.Vector3(.5,.5,.5),setting.strength);
            e.material.map=e.generated=map;
        } catch(error){e.material.map=source;
            if(e.base.pmxDiffuse)pmxDiffuse?.copy(e.base.pmxDiffuse);
            if(e.base.pmxAmbient)pmxAmbient?.copy(e.base.pmxAmbient);
            throw error;}
        finally {previous?.dispose();e.material.needsUpdate=true;}
    }
    async setRemap(id,blob) {
        const revision=this.revision;
        const e=this.entry(id);if(!e||e.kind==='art')throw Error('Choose a texture slot.');
        let replacement=null;
        if(blob){
            if(blob.size>16*1024*1024)throw Error('Replacement images must be under 16 MB.');
            const {source:image,width,height}=await decodeReplacementImage(blob);
            if(revision!==this.revision)throw Error('Model changed while loading this image. Choose its replacement again.');
            if(width*height>16777216)throw Error('Replacement images must be at most 4096 × 4096.');
            if(e.kind==='atlas')replacement=PIXI.Texture.from(image);
            else {
                replacement=new THREE.Texture();
                if(e.base.map)replacement.copy(e.base.map);else replacement.colorSpace=THREE.SRGBColorSpace;
                if(replacement.userData)delete replacement.userData.sakuraPmxFallback;
                // A decoded PNG/TGA canvas cannot reuse DDS block-compression
                // format or mipmaps. Keep UV transforms and the original map
                // for reset, but upload the replacement as normal RGBA pixels.
                if(e.base.map?.isCompressedTexture){replacement.format=THREE.RGBAFormat;replacement.type=THREE.UnsignedByteType;replacement.mipmaps=[];replacement.generateMipmaps=true;replacement.minFilter=THREE.LinearMipmapLinearFilter;}
                replacement.source=new THREE.Source(image);replacement.needsUpdate=true;
            }
        }
        const old=this.replacements.get(id);
        if(replacement)this.replacements.set(id,replacement);else this.replacements.delete(id);
        if(e.kind==='atlas')this.live.avatar.textures[e.index]=replacement||e.base;
        else this.applyMaterial(e);
        if(e.kind==='atlas')old?.destroy(true);else old?.dispose();
    }
    restore() {
        this.setHover(null);
        this.revision=(this.revision||0)+1;
        if(this.renderer&&this.drawOriginal)this.renderer.drawMesh=this.drawOriginal;
        for(const e of this.entries){
            if(e.kind==='material'){e.material.map=e.base.map;e.material.color.copy(e.base.color);if(e.base.pmxDiffuse)e.material.uniforms?.sakuraPmxDiffuse?.value.copy(e.base.pmxDiffuse);if(e.base.pmxAmbient)e.material.uniforms?.sakuraPmxAmbient?.value.copy(e.base.pmxAmbient);e.material.opacity=e.base.opacity;e.material.transparent=e.base.transparent;e.material.depthWrite=e.base.depthWrite;e.material.alphaTest=e.base.alphaTest;e.material.needsUpdate=true;e.generated?.dispose();}
            if(e.kind==='atlas'&&this.live?.avatar)this.live.avatar.textures[e.index]=e.base;
        }
        for(const [id,texture]of this.replacements){if(id.startsWith('atlas:'))texture.destroy(true);else texture.dispose();}
        this.replacements.clear();this.colors={};this.renderer=null;this.drawOriginal=null;
        this.entries=[];this.live=null;
    }
    setHover(id) {
        if(this.hoverMaterial){this.hoverMaterial.material.color.copy(this.hoverColor);this.hoverMaterial=null;}
        this.hoverId=id;
        const entry=this.entry(id);
        if(entry?.material){this.hoverMaterial=entry;this.hoverColor=entry.material.color.clone();entry.material.color.set('#48ffff');}
    }
    pick(x,y) {
        if(this.live){
            const avatar=this.live.avatar,internal=avatar.internalModel;
            const point=avatar.worldTransform.applyInverse(new PIXI.Point(x,y));
            const local=internal.localTransform.clone().invert().apply(point);
            const orders=this.core._model.drawables.renderOrders;
            const sorted=this.colorTargets().filter(e=>this.core.getDrawableOpacity(e.index)>.02).sort((a,b)=>orders[b.index]-orders[a.index]);
            for(const entry of sorted){
                const points=internal.getDrawableVertices(entry.index),indices=this.core.getDrawableVertexIndices(entry.index);
                for(let t=0;t<indices.length;t+=3){
                    const a=indices[t]*2,b=indices[t+1]*2,c=indices[t+2]*2;
                    const side=(u,v)=> (local.x-points[u])*(points[v+1]-points[u+1])-(local.y-points[u+1])*(points[v]-points[u]);
                    const d1=side(a,b),d2=side(b,c),d3=side(c,a);
                    if(!((d1<0||d2<0||d3<0)&&(d1>0||d2>0||d3>0)))return entry.id;
                }
            }return null;
        }
        const canvas=this.viewer.renderer.domElement,rect=canvas.getBoundingClientRect();
        this.ray ||= new THREE.Raycaster();this.pointer ||= new THREE.Vector2();
        this.pointer.set((x-rect.left)/rect.width*2-1,-(y-rect.top)/rect.height*2+1);
        this.ray.setFromCamera(this.pointer,this.viewer.camera);
        const hit=this.ray.intersectObject(this.viewer.model,true).find(h=>h.object.visible);
        if(!hit)return null;
        const m=Array.isArray(hit.object.material)?hit.object.material[hit.face.materialIndex]:hit.object.material;
        return this.entries.find(e=>e.material===m)?.id||null;
    }
}

export async function storedRemap(key,id,blob=undefined) {
    const db=await new Promise((resolve,reject)=>{const req=indexedDB.open('sakura-model-materials',1);req.onupgradeneeded=()=>req.result.createObjectStore('textures');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
    try{return await new Promise((resolve,reject)=>{
        const transaction=db.transaction('textures',blob===undefined?'readonly':'readwrite'),store=transaction.objectStore('textures'),record=key+'|'+id;
        const request=blob===undefined?store.get(record):blob===null?store.delete(record):store.put(blob,record);
        let result;request.onsuccess=()=>{result=request.result;};transaction.oncomplete=()=>resolve(result);transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error||Error('Texture could not be saved.'));
    });}finally{db.close();}
}
