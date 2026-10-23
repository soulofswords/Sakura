import * as THREE from 'three';
import {applyFaceMappings} from './live2d-face-mapping.js?v=2';
import {chatReaderLean} from './chat-reader-motion.js?v=1';
import {renderPixelRatio} from './render-budget.js?v=startup68';
import {installLive2DControls} from './live2d-controls.js?v=phone-touch73';
let runtime;
function script(src){return new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.onload=resolve;s.onerror=()=>reject(Error('Live2D runtime could not load: '+src));document.head.append(s);});}
async function ensureRuntime(){
    runtime ||= (async()=>{await script('/static/vendor/live2d/live2dcubismcore.min.js');await script('/static/vendor/live2d/pixi.min.js');await script('/static/vendor/live2d/cubism4.min.js');})();
    return runtime;
}
export default class Live2DViewer {
    static async create(url,owner){
        await ensureRuntime();const v=new Live2DViewer(owner);
        try{
            const response=await fetch(url);if(!response.ok)throw Error('Live2D model settings could not be read.');
            const settings=await response.json();settings.url=new URL(url,location.href).href;
            v.avatar=await PIXI.live2d.Live2DModel.from(settings,{autoUpdate:false,autoInteract:false});
            v.parameterLabels={};
            try{
                const displayRef=settings.FileReferences?.DisplayInfo||new URL(settings.url).pathname.split('/').pop().replace(/\.model3\.json$/i,'.cdi3.json');
                const displayUrl=new URL(displayRef,settings.url),base=new URL('.',settings.url);
                if(displayUrl.origin===base.origin&&displayUrl.pathname.startsWith(base.pathname)){
                    const display=await fetch(displayUrl);if(display.ok){const data=await display.json();for(const p of (data.Parameters||[]).slice(0,2000))if(typeof p.Id==='string'&&typeof p.Name==='string')v.parameterLabels[p.Id]=p.Name;}
                }
            }catch(_){/* Display names are optional; parameter IDs still work. */}
            v.installMaskRefresh();
            v.app.stage.addChild(v.avatar);
            let refs=settings.FileReferences?.Expressions||[];
            try{
                const modelPath=new URL(url,location.href).pathname.replace(/^\/models\//,'').split('/').map(decodeURIComponent).join('/');
                const discovered=await fetch('/api/models/live2d-expressions?model='+encodeURIComponent(modelPath),{cache:'no-store'});
                if(discovered.ok){const result=await discovered.json();if(Array.isArray(result.expressions)&&result.expressions.length)refs=result.expressions;}
            }catch(error){console.warn('Live2D sidecar expression scan unavailable; using model3.json references.',error);}
            for(const e of refs){const r=await fetch(new URL(e.File,settings.url));if(r.ok)v.expressions.set(e.Name,await r.json());}
            v.ensureExpressionManager(settings,refs);
            v.names=[...v.expressions.keys()];v.fit();
            const physicsRef=settings.FileReferences?.Physics;
            if(physicsRef){
                const physicsResponse=await fetch(new URL(physicsRef,settings.url));
                if(physicsResponse.ok){
                    const physics=await physicsResponse.json(),list=physics.PhysicsSettings||[];
                    v.physicsInfo={source:'Live2D authored physics',engine:'Cubism Physics',chains:list.length,
                        bones:list.reduce((sum,item)=>sum+(item.Vertices?.length||0),0)};
                }
            }
            v.physicsInfo ||= {source:'none',engine:'Cubism Physics',chains:0,bones:0};
            v.eyeBlink=v.avatar.internalModel.eyeBlink;
            const internal=v.avatar.internalModel,natural=internal.updateNaturalMovements,focus=internal.updateFocus;
            internal.updateNaturalMovements=function(...args){
                if(!owner.userTracking&&!owner.vtuberTrackingMode)return natural.apply(this,args);
            };
            internal.updateFocus=function(...args){
                if(!owner.userTracking)return focus.apply(this,args);
            };
            // Authored Cubism physics often routes tracking inputs into a
            // second visible parameter (e.g. ParamAngleX -> ParamAngleX_M).
            // Supply inputs before physics, not after it has already run.
            v.avatar.internalModel.on('afterMotionUpdate',()=>v.applyParameters());
            v.avatar.internalModel.on('beforeModelUpdate',()=>v.applyManualExpressions());
            v.app.view.style.visibility='visible';return v;
        }catch(error){v.destroy();throw error;}
    }
    constructor(owner){
        this.owner=owner;this.expressions=new Map();this.values={};this.filtered={};this.neutral=null;this.pan={x:0,y:0};
        this.gazeTarget=null;this.gazePosition={x:0,y:0};
        this.motion={time:0,talkBlend:0,settle:0,wasTalking:false};
        const initialWidth=Math.max(1,owner.container.clientWidth||innerWidth),initialHeight=Math.max(1,owner.container.clientHeight||innerHeight);
        this.app=new PIXI.Application({width:initialWidth,height:initialHeight,backgroundAlpha:0,antialias:true,preserveDrawingBuffer:true,autoStart:false,sharedTicker:false,resolution:renderPixelRatio(initialWidth,initialHeight,Math.min(devicePixelRatio,2))});
        Object.assign(this.app.view.style,{position:'absolute',inset:'0',width:'100%',height:'100%',visibility:'hidden'});
        owner.container.append(this.app.view);
        installLive2DControls(this.app.view,owner,this);
        this.app.view.addEventListener('wheel',e=>{e.preventDefault();owner.setDisplaySize(owner.camera.zoom*100+(e.deltaY<0?5:-5));},{passive:false});
        this.app.view.addEventListener('dblclick',()=>{this.pan={x:0,y:0};this.fit();});
    }
    fit(){
        if(!this.avatar)return;
        const w=Math.max(1,this.owner.container.clientWidth||innerWidth),h=Math.max(1,this.owner.container.clientHeight||innerHeight);const resolution=renderPixelRatio(w,h,Math.min(devicePixelRatio*({low:.75,balanced:1.25,high:2}[this.owner.quality]||1),2));
        if(this.app.renderer.resolution!==resolution || this.app.screen.width!==w || this.app.screen.height!==h){this.app.renderer.resolution=resolution;this.app.renderer.resize(w,h);}
        const m=this.avatar.internalModel;
        // Live2D is a 2D stage: changing the Three.js camera cannot frame it.
        // Portrait frames the upper 60% of the authored canvas; full view fits all of it.
        const full=this.owner.fullModelView || this.owner.desktopMode;
        const visibleHeight=m.originalHeight*(full?1:.6);
        const scale=Math.min(w/m.originalWidth,h/visibleHeight)*.92*this.owner.camera.zoom;
        this.avatar.scale.set(scale);this.avatar.anchor.set(.5,full?.5:.3);this.avatar.position.set(w/2+this.pan.x,h/2+this.pan.y);
    }
    calibrate(){const face=this.owner.userTrackingSample?.face,matrix=face?.matrix;if(matrix)this.neutral=new THREE.Euler().setFromRotationMatrix(new THREE.Matrix4().fromArray(matrix),'XYZ');
        this.eyeNeutral={};for(const [side,ids]of [['L',[33,133,159,145]],['R',[362,263,386,374]]]){
            const p=face?.landmarks;if(!ids.every(i=>p?.[i]))continue;
            const ratio=Math.hypot(p[ids[2]].x-p[ids[3]].x,p[ids[2]].y-p[ids[3]].y)/Math.max(.001,Math.hypot(p[ids[0]].x-p[ids[1]].x,p[ids[0]].y-p[ids[1]].y));
            if(Number.isFinite(ratio)&&ratio>.06)this.eyeNeutral[side]=Math.max(.08,Math.min(.5,ratio));
        }
    }
    installMaskRefresh(){
        const core=this.avatar.internalModel.coreModel;
        // The bundled Cubism renderer clears its mask atlas, then skips
        // unchanged mask vertices. Opacity-only expressions can reveal a
        // drawable with an empty/stale mask tile (a rectangular black patch).
        // Redraw mask sources, including static meshes; leave other flags intact.
        const sources=new Set();
        for(let i=0;i<core.getDrawableCount();i++)for(const index of core.getDrawableMasks()[i]||[])sources.add(index);
        const original=core.getDrawableDynamicFlagVertexPositionsDidChange.bind(core);
        core.getDrawableDynamicFlagVertexPositionsDidChange=index=>sources.has(index)||original(index);
        this.maskSources=sources.size;
    }
    setMorph(name,value){this.values[name]=value;}
    ensureExpressionManager(settings,refs){
        const motionManager=this.avatar?.internalModel?.motionManager;
        if(motionManager?.expressionManager||!refs.length)return !!motionManager?.expressionManager;
        const ExpressionManager=PIXI.live2d.Cubism4ExpressionManager;
        if(!ExpressionManager)return false;
        motionManager.expressionManager=new ExpressionManager({...settings,expressions:refs});
        return true;
    }
    setGazeTarget(x,y){
        this.gazeTarget={x:Math.max(-1,Math.min(1,x)),y:Math.max(-1,Math.min(1,y))};
    }
    clearGaze(){
        this.gazeTarget=null;this.gazePosition={x:0,y:0};
        this.avatar?.internalModel?.focusController?.focus(0,0,true);
    }
    setExpression(name,weight=1){
        if(!this.expressions.has(name))return false;
        const amount=Number(weight);if(!Number.isFinite(amount))return false;
        this.activeExpressions ||= new Map();this.activeExpressions.delete(name);this.activeExpressions.set(name,Math.max(0,Math.min(1,amount)));
        this.avatar.internalModel.motionManager?.expressionManager?.stopAllExpressions();
        return true;
    }
    removeExpression(name){this.activeExpressions?.delete(name);}
    applyManualExpressions(){
        const sample=this.owner?.userTrackingSample,fresh=sample&&performance.now()-sample.receivedAt<600;
        const native=fresh&&sample.face?.nativeExpressions;
        const ordinary=fresh?Object.fromEntries((sample.face?.blendshapes||[]).map(b=>[b.categoryName,b.score])):{};
        if(this.faceSignalMapping||this.faceSignalPreview)applyFaceMappings(this,this.faceSignalPreview||native||ordinary,this.faceSignalMapping,!!this.faceSignalPreview||!!(fresh&&this.owner.userTracking&&this.owner.trackingMouthEnabled!==false));
        // Inactive camera mappings can reset jawOpen to zero. Audible output
        // owns the mouth after those mappings, before user expressions.
        this.applyAudioMouth();
        const core=this.avatar.internalModel.coreModel;
        if(this.chatReaderPose&&!this.owner.userTracking){
            const ids=Array.from(core._model?.parameters?.ids||[]);
            for(const [id,value]of Object.entries(this.chatReaderPose))if(ids.includes(id))core.setParameterValueById(id,value);
        }
        for(const [name,amount]of this.activeExpressions||[]) {
            for(const p of this.expressions.get(name)?.Parameters||[]) {
                // Cubism creates virtual indices for unknown IDs. Those have
                // no drawable effect and must not receive invalid values.
                const ids=core._model?.parameters?.ids;
                if(ids&&!Array.from(ids).includes(p.Id))continue;
                if(!Number.isFinite(p.Value))continue;
                const index=core.getParameterIndex(p.Id);if(index<0)continue;
                const base=core.getParameterValueByIndex(index);
                const next=p.Blend==='Multiply'?base*(1+(p.Value-1)*amount):p.Blend==='Overwrite'?base+(p.Value-base)*amount:base+p.Value*amount;
                if(Number.isFinite(next))core.setParameterValueByIndex(index,next);
            }
        }
    }
    clearExpression(){this.activeExpressions?.clear();this.avatar?.internalModel?.motionManager?.expressionManager?.stopAllExpressions();}
    applyAudioMouth(){
        if(!this.owner?.audioPlaybackActive)return;
        const core=this.avatar.internalModel.coreModel,ids=Array.from(core._model?.parameters?.ids||[]);
        const set=(id,value)=>{if(ids.includes(id)&&Number.isFinite(value))core.setParameterValueById(id,value);};
        const opening=Math.max(...['A','I','U','E','O'].map(k=>Number(this.values[k])||0),0);
        set('ParamMouthOpenY',opening);set('ParamMouthForm',opening>0?.12+opening*.35:0);
        for(const name of Object.values(this.owner.mouthOptions?.mapping||{}))if(name&&name!=='none'&&Object.hasOwn(this.values,name))set(name,this.values[name]);
    }
    applyParameters(){
        const core=this.avatar.internalModel.coreModel,o=this.owner;
        const set=(id,value)=>{if(core.getParameterIndex(id)>=0)core.setParameterValueById(id,value);};
        const dt=this.renderDelta??1/60;
        // Match the 3D retargeter's user-controlled response. A 12ms head
        // filter snapped to each camera packet and then held until the next
        // packet, exposing the 15/24Hz steps in the 60Hz Live2D render loop.
        const smoothing=THREE.MathUtils.clamp(Number(o.trackingOptions?.smoothing??.25),0,1);
        const headResponse=.02+smoothing*.2;
        const smooth=(id,value)=>{const tau=/^ParamAngle[XYZ]$/.test(id)&&o.userTracking?headResponse:/^Param(?:Eye|Mouth)/.test(id)?.018:.035,alpha=1-Math.exp(-dt/tau);this.filtered[id]=(this.filtered[id]??value)+(value-(this.filtered[id]??value))*alpha;set(id,this.filtered[id]);};
        if(o.userTracking){
            const sample=o.userTrackingSample,fresh=sample&&performance.now()-sample.receivedAt<600;
            const face=fresh&&sample.face?.landmarks?.length?sample.face:null;
            const scores=Object.fromEntries((face?.blendshapes||[]).map(b=>[b.categoryName,b.score]));
            const hasPose=face?.matrix?.length===16&&Array.from(face.matrix).every(Number.isFinite);
            let rotation=new THREE.Euler();if(hasPose){rotation.setFromRotationMatrix(new THREE.Matrix4().extractRotation(new THREE.Matrix4().fromArray(face.matrix)),'XYZ');this.neutral ||= rotation.clone();}
            const headReady=hasPose&&this.neutral;
            const sign=o.userTrackingMirror===false?-1:1,range=o.trackingOptions?.range??1;
            const clamp=x=>Math.max(0,Math.min(1,x));
            smooth('ParamAngleX',headReady?(rotation.y-this.neutral.y)*sign*57.3*range:0);
            smooth('ParamAngleY',headReady?-(rotation.x-this.neutral.x)*57.3*range:0);
            smooth('ParamAngleZ',headReady?-(rotation.z-this.neutral.z)*sign*57.3*range:0);
            const aperture=(a,b,c,d)=>{const p=face?.landmarks;if(!p?.[d])return null;return Math.hypot(p[c].x-p[d].x,p[c].y-p[d].y)/Math.max(.001,Math.hypot(p[a].x-p[b].x,p[a].y-p[b].y));};
            for(const [side,ids] of [['L',[33,133,159,145]],['R',[362,263,386,374]]]){
                const ratio=aperture(...ids),blink=scores[side==='L'?'eyeBlinkLeft':'eyeBlinkRight']||0;
                let closure=Math.max(clamp(blink*1.6),ratio===null?0:clamp((.23-ratio)/.14));
                if(o.trackingOptions?.glasses&&ratio!==null){
                    this.eyeNeutral||={};this.eyeNeutral[side]??=Math.max(.08,Math.min(.5,ratio));
                    const relative=ratio/this.eyeNeutral[side],landmarkClosure=clamp((1-relative-.15)/.65);
                    closure=Math.max(landmarkClosure*landmarkClosure*(3-2*landmarkClosure),clamp(blink*1.6)*clamp((.85-relative)/.45));
                }
                smooth('ParamEye'+side+'Open',face?1-closure:1);
            }
            if(o.trackingMouthEnabled!==false&&!o.audioPlaybackActive){
                const mouth=aperture(61,291,13,14);
                smooth('ParamMouthOpenY',Math.max(clamp((scores.jawOpen||0)*1.5),mouth===null?0:clamp((mouth-.035)*5)));
                smooth('ParamMouthForm',Math.max(scores.mouthSmileLeft||0,scores.mouthSmileRight||0));
            }else{
                const mouth=Math.max(...['A','I','U','E','O'].map(k=>this.values[k]||0),0);
                smooth('ParamMouthOpenY',mouth);smooth('ParamMouthForm',0);
            }
        }else{
            const mouth=Math.max(...['A','I','U','E','O'].map(k=>this.values[k]||0),0);
            smooth('ParamMouthOpenY',mouth);smooth('ParamMouthForm',o.activity==='talking'?.12+mouth*.35:0);
            const blink=o.vtuberTrackingMode?0:Math.pow(Math.max(0,Math.cos(performance.now()/1000*1.1)),40);
            set('ParamEyeLOpen',1-blink);set('ParamEyeROpen',1-blink);
            if(!o.vtuberTrackingMode){
                const now=performance.now()/1000,dt=Math.min(.05,Math.max(0,now-(this.motion.lastTime??now)));
                this.motion.lastTime=now;
                const speaking=o.activity==='talking';
                this.motion.talkBlend+=(Number(speaking)-this.motion.talkBlend)*(1-Math.exp(-dt/.22));
                if(this.motion.wasTalking&&!speaking)this.motion.settle=1;
                this.motion.wasTalking=speaking;
                this.motion.settle=Math.max(0,this.motion.settle-dt/2.4);
                if(speaking)this.motion.time+=dt;
                const beat=Math.sin(this.motion.time*2.4)*Math.sin(this.motion.time*.65);
                const speech=this.motion.talkBlend*(.3+(o.speechLevel||0)*.7);
                const idle=Math.sin(now*.42)*.45;
                smooth('ParamBodyAngleZ',idle+beat*1.35*speech+Math.sin(now*1.4)*.8*this.motion.settle);
                smooth('ParamBodyAngleX',Math.sin(this.motion.time*1.4)*.8*speech);
                smooth('ParamAngleX',Math.sin(this.motion.time*1.7)*1.8*speech+Math.sin(now*.5)*.25);
                smooth('ParamBreath',.5+Math.sin(now*1.6)*.08);
            }
        }
        // Direct parameter remaps allow models with custom Cubism mouth IDs.
        this.chatReaderPose=null;
        if(o.vtuberTrackingMode&&(o.chatReaderActive||o.chatReaderMotion)){
            const lean=chatReaderLean(o,this.renderDelta??1/60);
            if(lean!==null){this.chatReaderPose={ParamBodyAngleZ:lean*57.3,ParamAngleZ:-lean*57.3*.25};for(const [id,value]of Object.entries(this.chatReaderPose))set(id,value);}
        }
        for(const name of Object.values(o.mouthOptions?.mapping||{}))if(name&&name!=='none'&&Object.hasOwn(this.values,name))set(name,this.values[name]);
        if(o.mouthOptions?.source==='off'&&!o.audioPlaybackActive){set('ParamMouthOpenY',0);set('ParamMouthForm',0);}
        if(o.mouthOptions?.source==='both'&&o.microphoneMouthWeights){const i=core.getParameterIndex('ParamMouthOpenY');if(i>=0)set('ParamMouthOpenY',Math.max(core.getParameterValueByIndex(i),...Object.values(o.microphoneMouthWeights)));}
    }
    render(delta){
        this.renderDelta=Math.max(0,Math.min(delta,.1));
        const internal=this.avatar.internalModel;
        if(this.gazeTarget){
            const alpha=1-Math.exp(-Math.min(delta,.1)/.055);
            this.gazePosition.x+=(this.gazeTarget.x-this.gazePosition.x)*alpha;
            this.gazePosition.y+=(this.gazeTarget.y-this.gazePosition.y)*alpha;
            this.avatar.focus((this.gazePosition.x+1)*innerWidth/2,(this.gazePosition.y+1)*innerHeight/2,true);
        }
        internal.eyeBlink=this.owner.vtuberTrackingMode?undefined:this.eyeBlink;
        const physics=internal.physics;
        if(this.owner.physics.mode==='off')internal.physics=undefined;
        try{this.avatar.update(Math.min(delta,.05)*1000);this.app.renderer.render(this.app.stage);}
        finally{internal.physics=physics;}
    }
    capture(maxSize=720){
        const canvas=this.app.renderer.extract.canvas(this.app.stage),scale=Math.min(1,maxSize/Math.max(canvas.width,canvas.height));
        const target=document.createElement('canvas');target.width=Math.max(1,Math.round(canvas.width*scale));target.height=Math.max(1,Math.round(canvas.height*scale));
        const ctx=target.getContext('2d');ctx.drawImage(canvas,0,0,target.width,target.height);
        return {pixels:new Uint8Array(ctx.getImageData(0,0,target.width,target.height).data),width:target.width,height:target.height,canvas:target};
    }
    destroy(){this.avatar?.destroy({children:true,texture:true,baseTexture:true});this.app.destroy(true,{children:true,texture:true,baseTexture:true});}
}
