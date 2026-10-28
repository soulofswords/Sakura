// Local rig diagnostics. Screenshots are evidence for a human, not a bone
// classifier: only sustained, measured corruption can freeze a physics bone.
function stableSignature(value){return JSON.stringify(value,(_,number)=>typeof number==='number'&&Number.isFinite(number)?Math.round(number*100000)/100000:number);}
export default class ModelRigMonitor {
    constructor(viewer){this.viewer=viewer;this.run=0;this.lastSample=0;this.vrmRest=new WeakMap();this.nodes=[];this.samples=new Map();this.finished=true;}
    key(){return 'sakura_rig_analysis:'+this.url;}
    start(url){
        this.viewer.rigAnalysis=null;this.viewer.rigDiagnosticImage=null;
        this.run++;this.url=this.viewer.repairStore?'/models/'+this.viewer.repairStore.key(url):url.split(/[?#]/,1)[0];this.samples=new Map();this.started=performance.now();this.finished=false;
        this.referenceCaptured=false;this.referenceImage=null;this.viewer.rigDiagnosticReference=null;this.lastSample=0;
        this.manualRepair=false;
        const physics=this.viewer.physics;
        this.nodes=/\.vrm$/i.test(this.url)?(physics.vrmPhysicsJoints||[]).filter(j=>j.bone).map((joint,index)=>{
            if(!this.vrmRest.has(joint.bone))this.vrmRest.set(joint.bone,{restLocal:joint.bone.position.clone(),restQuat:joint.bone.quaternion.clone()});
            return {index,bone:joint.bone,...this.vrmRest.get(joint.bone),joint};
        }):physics.nodes||[];
        this.viewer.diagnosticFrozenBones=new Set();
        if(!/\.(?:pmx|vrm)$/i.test(this.url)||!this.nodes.length){this.finished=true;return;}
        this.signature=stableSignature(this.nodes.map(n=>[n.index,n.bone.name,n.restLocal.toArray(),n.restQuat.toArray()]));
        let saved;try{saved=this.viewer.repairStore?this.viewer.repairStore.diagnostic(this.url):JSON.parse(localStorage.getItem(this.key())||'null');}catch(_){}
        let sameRig=saved?.signature===this.signature;
        if(saved&&!sameRig)try{sameRig=stableSignature(JSON.parse(saved.signature))===this.signature;}catch(_){}
        const frozen=sameRig&&Array.isArray(saved.frozen)?saved.frozen:[];
        for(const node of this.nodes){node.diagnosticStatic=frozen.includes(node.index);if(node.diagnosticStatic)this.viewer.diagnosticFrozenBones.add(node.bone);}
        this.viewer._syncVrmPhysics?.();
        if(frozen.length)this.applyFrozen();
        this.viewer.rigAnalysis={status:`Taking local model screenshots and checking physics for 8 seconds…${frozen.length?' Saved freezes applied.':''}`,frozen};
        window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:this.viewer.rigAnalysis}));
    }
    sample(now=performance.now()){
        if(this.finished||now-this.lastSample<100)return;
        this.lastSample=now;
        if(!this.referenceCaptured&&now-this.started>=2000){this.referenceCaptured=true;this.capture('reference');}
        const physics=this.viewer.physics;
        // Off has no motion to diagnose. Do not flag camera gestures or an
        // authored tracking pose as physics instability.
        if(physics.mode!=='off')for(const node of this.nodes){
            if(node.diagnosticStatic)continue;
            const q=node.bone.quaternion,p=node.bone.position;
            let s=this.samples.get(node.index);if(!s){s={bad:0,total:0,previous:q.clone(),jitter:0,outsideLimit:0,collisionConflict:0,persistentBend:0};this.samples.set(node.index,s);}
            const finite=[q.x,q.y,q.z,q.w,p.x,p.y,p.z].every(Number.isFinite);
            const stretch=finite&&p.distanceTo(node.restLocal)>Math.max(.5,node.restLocal.length()*1.5);
            const angle=finite?q.angleTo(node.attachedRibbon&&node.hangingQuat?node.hangingQuat:node.restQuat):Math.PI;
            const jump=finite?q.angleTo(s.previous):Math.PI;
            s.total++;if(!finite||stretch)s.bad++;
            if(angle>2.6&&jump>1.2)s.jitter++;
            const limit=node.params?.maxAngle;
            if(finite&&Number.isFinite(limit)&&angle>(limit+15)*Math.PI/180)s.outsideLimit++;
            if(node.collisionConflict)s.collisionConflict++;
            if(node.category==='hair'&&finite&&angle>Math.max(25,(limit||50)*.6)*Math.PI/180)s.persistentBend++;
            s.previous.copy(q);
        }
        if(now-this.started<8000)return;
        this.finished=true;
        const prior=this.nodes.filter(n=>n.diagnosticStatic).map(n=>n.index);
        let found=[...this.samples].filter(([,s])=>s.bad>=3||(s.total>=30&&(s.jitter>=12||s.outsideLimit>=Math.max(20,s.total*.7)||s.collisionConflict>=Math.max(20,s.total*.7)||(this.manualRepair&&(s.collisionConflict>=Math.max(5,s.total*.1)||s.persistentBend>=s.total*.4))))).map(([id])=>id);
        if(this.manualRepair){
            const byBone=new Map(this.nodes.map(n=>[n.bone,n]));
            const root=node=>{let current=node;while(byBone.get(current.bone.parent)?.category==='hair')current=byBone.get(current.bone.parent);return current.index;};
            const affected=new Set(this.nodes.filter(n=>n.category==='hair'&&found.includes(n.index)).map(root));
            found=[...new Set([...found,...this.nodes.filter(n=>n.category==='hair'&&affected.has(root(n))).map(n=>n.index)])];
        }
        const frozen=[...new Set([...prior,...found])];
        const report={version:2,signature:this.signature,frozen,checkedAt:new Date().toISOString(),
            bones:this.nodes.length,findings:found.map(id=>({index:id,name:this.nodes.find(n=>n.index===id)?.bone.name,measurements:this.samples.get(id)||{chainRepair:true}}))};
        for(const finding of report.findings)delete finding.measurements.previous;
        try{localStorage.setItem(this.key(),JSON.stringify(report));}catch(_){}
        this.viewer.rigAnalysis={...report,status:found.length?`${found.length} unstable physics bones detected; held at rest on next load.`:prior.length?`${prior.length} unstable physics bones held at rest.`:'Physics check complete: no sustained instability detected.'};
        if(this.manualRepair&&frozen.length){
            for(const node of this.nodes)if(frozen.includes(node.index)){node.diagnosticStatic=true;this.viewer.diagnosticFrozenBones.add(node.bone);}
            this.applyFrozen();
            this.viewer.rigAnalysis.status=`${frozen.length} bones frozen now. Repair saved for future loads.`;
        }
        this.persist(report);
        this.capture('diagnostic',report);
        window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:this.viewer.rigAnalysis}));
    }
    capture(kind,report=this.viewer.rigAnalysis){
        const generation=this.viewer.loadGeneration,run=this.run;
        try{
            const frame=this.viewer.captureSpoutFrame(480);
            if(frame){const canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
                canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
                canvas.toBlob(blob=>{if(blob&&run===this.run&&generation===this.viewer.loadGeneration){
                    if(kind==='reference'){this.referenceImage=blob;this.viewer.rigDiagnosticReference=blob;}
                    else{this.viewer.rigDiagnosticImage=blob;this.storeImage(blob,report);}
                }},'image/png');}
        }catch(error){console.warn('Model diagnostic image unavailable:',error);}
    }
    storeImage(blob,report){
        const request=indexedDB.open('sakura-rig-diagnostics',1);
        request.onupgradeneeded=()=>request.result.createObjectStore('models');
        const url=this.url;
        const reference=this.referenceImage;
        request.onsuccess=()=>{const db=request.result,tx=db.transaction('models','readwrite');tx.objectStore('models').put({blob,reference,report},url);tx.oncomplete=()=>db.close();tx.onerror=()=>db.close();};
    }
    persist(report){
        if(!this.viewer.repairStore)return;
        const run=this.run,analysis=this.viewer.rigAnalysis;
        const complete=status=>{if(run!==this.run||this.viewer.rigAnalysis!==analysis)return;analysis.status=status;window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:analysis}));};
        complete(report.frozen.length?'Saving bone repairs…':'Saving completed bone check…');
        void this.viewer.repairStore.saveDiagnostic(this.url,report).then(()=>complete(report.frozen.length?`${report.frozen.length} bone repairs saved for future launches.`:'Bone check saved: no sustained instability detected.'),error=>complete('Repair could not be saved: '+error.message));
    }
    enforce(){
        for(const node of this.nodes||[])if(node.diagnosticStatic){node.bone.position.copy(node.restLocal);node.bone.quaternion.copy(node.restQuat);node.bone.updateMatrix();}
    }
    applyFrozen(){
        // Both PMX spring nodes and native VRM joints must receive the saved
        // rest transform immediately; updating a UI flag alone is insufficient.
        for(const node of this.nodes||[])if(node.diagnosticStatic){node.bone.position.copy(node.restLocal);node.bone.quaternion.copy(node.restQuat);node.bone.updateMatrix();}
        this.viewer.model?.updateMatrixWorld?.(true);this.viewer.physics.reset?.();this.viewer._syncVrmPhysics?.();
    }
    checkNow(){
        if(!this.url||!this.viewer.model)return false;
        this.start(this.url);
        if(this.finished)return false;
        this.manualRepair=true;
        this.referenceCaptured=true;this.capture('reference');
        this.viewer.rigAnalysis.status='Snapshot captured. Checking hair, clothing and other physics bones for eight seconds; confirmed repairs apply immediately and are saved.';
        window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:this.viewer.rigAnalysis}));return true;
    }
    unfreezeBone(bone){
        for(const node of this.nodes||[])if(node.bone===bone)node.diagnosticStatic=false;
        this.viewer.diagnosticFrozenBones?.delete(bone);this.viewer._syncVrmPhysics?.();
        let saved;try{saved=this.viewer.repairStore?this.viewer.repairStore.diagnostic(this.url):JSON.parse(localStorage.getItem(this.key())||'null');}catch(_){}
        const frozen=(this.nodes||[]).filter(n=>n.diagnosticStatic).map(n=>n.index);
        const report={...(saved||{}),signature:this.signature,frozen};
        try{localStorage.setItem(this.key(),JSON.stringify(report));}catch(_){}
        this.viewer.rigAnalysis={...report,status:`${frozen.length} automatically frozen bones. Selected bone restored.`};
        this.persist(report);
        window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:this.viewer.rigAnalysis}));
    }
    reset(){if(!this.url)return;try{localStorage.removeItem(this.key());}catch(_){}if(this.viewer.repairStore)void this.viewer.repairStore.saveDiagnostic(this.url,null).catch(error=>console.warn('Bone reset could not be saved:',error));for(const node of this.nodes||[])node.diagnosticStatic=false;this.start(this.url);}
}
