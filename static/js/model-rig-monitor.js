// Local rig diagnostics. Screenshots are evidence for a human, not a bone
// classifier: only sustained, measured corruption can freeze a physics bone.
export default class ModelRigMonitor {
    constructor(viewer){this.viewer=viewer;this.run=0;this.lastSample=0;}
    key(){return 'sakura_rig_analysis:'+this.url;}
    start(url){
        this.viewer.rigAnalysis=null;this.viewer.rigDiagnosticImage=null;
        this.run++;this.url=url;this.samples=new Map();this.started=performance.now();this.finished=false;
        const physics=this.viewer.physics;
        if(!/\.pmx(?:\?|$)/i.test(url)||!physics.nodes?.length){this.finished=true;return;}
        this.signature=JSON.stringify(physics.nodes.map(n=>[n.index,n.bone.name,n.restLocal.toArray(),n.restQuat.toArray()]));
        let saved;try{saved=JSON.parse(localStorage.getItem(this.key())||'null');}catch(_){}
        const frozen=saved?.signature===this.signature&&Array.isArray(saved.frozen)?saved.frozen:[];
        for(const node of physics.nodes)node.diagnosticStatic=frozen.includes(node.index);
        this.viewer.rigAnalysis={status:'Analyzing physics for 8 seconds…',frozen:frozen.length};
    }
    sample(now=performance.now()){
        if(this.finished||now-this.lastSample<100)return;
        this.lastSample=now;
        const physics=this.viewer.physics;
        // Off has no motion to diagnose. Do not flag camera gestures or an
        // authored tracking pose as physics instability.
        if(physics.mode!=='off')for(const node of physics.nodes){
            if(node.diagnosticStatic)continue;
            const q=node.bone.quaternion,p=node.bone.position;
            let s=this.samples.get(node.index);if(!s){s={bad:0,total:0,previous:q.clone(),jitter:0};this.samples.set(node.index,s);}
            const finite=[q.x,q.y,q.z,q.w,p.x,p.y,p.z].every(Number.isFinite);
            const stretch=finite&&p.distanceTo(node.restLocal)>Math.max(.5,node.restLocal.length()*1.5);
            const angle=finite?q.angleTo(node.restQuat):Math.PI;
            const jump=finite?q.angleTo(s.previous):Math.PI;
            s.total++;if(!finite||stretch)s.bad++;
            if(angle>2.6&&jump>1.2)s.jitter++;
            s.previous.copy(q);
        }
        if(now-this.started<8000)return;
        this.finished=true;
        const prior=physics.nodes.filter(n=>n.diagnosticStatic).map(n=>n.index);
        const found=[...this.samples].filter(([,s])=>s.bad>=3||(s.total>=30&&s.jitter>=12)).map(([id])=>id);
        const frozen=[...new Set([...prior,...found])];
        const report={version:1,signature:this.signature,frozen,checkedAt:new Date().toISOString(),
            bones:physics.nodes.length,findings:found.map(id=>({index:id,name:physics.nodes.find(n=>n.index===id)?.bone.name}))};
        try{localStorage.setItem(this.key(),JSON.stringify(report));}catch(_){}
        this.viewer.rigAnalysis={...report,status:found.length?`${found.length} unstable physics bones detected; held at rest on next load.`:prior.length?`${prior.length} unstable physics bones held at rest.`:'Physics check complete: no sustained instability detected.'};
        const generation=this.viewer.loadGeneration,run=this.run;
        try{
            const frame=this.viewer.captureSpoutFrame(480);
            if(frame){const canvas=document.createElement('canvas');canvas.width=frame.width;canvas.height=frame.height;
                canvas.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(frame.pixels),frame.width,frame.height),0,0);
                canvas.toBlob(blob=>{if(blob&&run===this.run&&generation===this.viewer.loadGeneration){this.viewer.rigDiagnosticImage=blob;this.storeImage(blob,report);}},'image/png');}
        }catch(error){console.warn('Model diagnostic image unavailable:',error);}
        window.dispatchEvent(new CustomEvent('sakura-rig-analysis',{detail:this.viewer.rigAnalysis}));
    }
    storeImage(blob,report){
        const request=indexedDB.open('sakura-rig-diagnostics',1);
        request.onupgradeneeded=()=>request.result.createObjectStore('models');
        const url=this.url;
        request.onsuccess=()=>{const db=request.result,tx=db.transaction('models','readwrite');tx.objectStore('models').put({blob,report},url);tx.oncomplete=()=>db.close();tx.onerror=()=>db.close();};
    }
    reset(){try{localStorage.removeItem(this.key());}catch(_){}for(const node of this.viewer.physics.nodes||[])node.diagnosticStatic=false;this.start(this.url);}
}
