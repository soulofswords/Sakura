const patterns={smile:/happy|smile|joy|laugh|にこ|笑|开心/i,surprise:/surpris|shock|驚|惊/i,sad:/sad|worr|悲|哀|困|难过/i,angry:/angry|anger|angery|怒|生气/i};
const unsafe=/outfit|cloth|dress|nude|undress|remove|toggle|accessor|weapon|hide|衣|服|脱|消|mouth|jaw|blink|ウィンク|まばたき/i;
export function autoExpressionMapping(viewer){
    const names=(viewer.allMorphNames||[]).filter(name=>!unsafe.test(name));
    return Object.fromEntries(Object.entries(patterns).map(([signal,pattern])=>[signal,names.find(name=>pattern.test(name))||'']));
}
export class AutoExpressions {
    constructor(viewer,key){this.viewer=viewer;this.key=key;this.root=viewer.live2d||viewer.model;this.weights={};
        try{const saved=JSON.parse(localStorage.getItem('sakura_auto_expressions:'+key)||'{}');this.enabled=saved.enabled===true;this.mapping={...autoExpressionMapping(viewer),...saved.mapping};}catch(_){this.enabled=false;this.mapping=autoExpressionMapping(viewer);}
    }
    save(){localStorage.setItem('sakura_auto_expressions:'+this.key,JSON.stringify({enabled:this.enabled,mapping:this.mapping}));}
    clear(){if(this.root===(this.viewer.live2d||this.viewer.model))for(const name of Object.keys(this.weights))if(!this.viewer.manualExpressions?.has(name)){if(this.viewer.live2d)this.viewer.live2d.removeExpression(name);else this.viewer.setMorph(name,0);}this.weights={};}
    update(delta){
        const v=this.viewer;if(this.root!==(v.live2d||v.model)||!this.enabled||!v.vtuberTrackingMode||!v.userTracking){this.clear();return;}
        const sample=v.userTrackingSample,fresh=sample&&performance.now()-sample.receivedAt<600;
        const s=Object.fromEntries((fresh?sample.face?.blendshapes||[]:[]).map(b=>[b.categoryName,Number(b.score)||0]));
        const signals={smile:Math.max(s.mouthSmileLeft||0,s.mouthSmileRight||0),surprise:Math.min(s.jawOpen||0,Math.max(s.browInnerUp||0,s.eyeWideLeft||0,s.eyeWideRight||0)),sad:Math.min(s.browInnerUp||0,Math.max(s.mouthFrownLeft||0,s.mouthFrownRight||0)),angry:Math.min(s.browDownLeft||0,s.browDownRight||0)};
        const targets={};for(const [signal,name]of Object.entries(this.mapping))if(name&&(v.allMorphNames||[]).includes(name))targets[name]=Math.max(targets[name]||0,Math.min(1,Math.max(0,(signals[signal]||0)-.2)/.6));
        const alpha=1-Math.exp(-Math.max(0,Math.min(.1,delta))/.18);
        for(const name of new Set([...Object.keys(this.weights),...Object.keys(targets)])){
            const weight=(this.weights[name]||0)+((targets[name]||0)-(this.weights[name]||0))*alpha;this.weights[name]=weight;
            if(v.manualExpressions?.has(name))continue;
            if(v.live2d){if(weight>.005)v.live2d.setExpression(name,weight);else v.live2d.removeExpression(name);}else v.setMorph(name,weight*.7);
        }
    }
}
export function installAutoExpressions(getViewer,getKey){
    const toggle=document.getElementById('expression-auto-enabled'),list=document.getElementById('expression-auto-mappings'),status=document.getElementById('expression-auto-status');let controller,identity,key;
    function refresh(){const viewer=getViewer(),root=viewer?.live2d||viewer?.model,newKey=getKey();if(!root)return;
        if(identity!==root||key!==newKey){controller?.clear();identity=root;key=newKey;controller=new AutoExpressions(viewer,key);viewer.autoExpressions=controller;}
        toggle.checked=controller.enabled;list.replaceChildren();
        for(const signal of Object.keys(patterns)){const label=document.createElement('label');label.textContent=signal;const select=document.createElement('select');select.add(new Option('Not mapped',''));for(const name of viewer.allMorphNames||[])select.add(new Option(name,name));select.value=controller.mapping[signal]||'';select.onchange=()=>{controller.clear();controller.mapping[signal]=select.value;controller.save();};label.append(select);list.append(label);}
        status.textContent='Camera-based expressions, no AI. Automatic matches use expression names; choose a mapping for unnamed expressions. Manual expressions take priority.';
    }
    toggle.onchange=()=>{if(!controller)return;controller.enabled=toggle.checked;controller.save();if(!controller.enabled)controller.clear();};
    return{refresh};
}
