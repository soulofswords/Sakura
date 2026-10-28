// PMX material morphs are sparse material operations, not GPU vertex targets.
export function collectMaterialControls(data){
    if(data.metadata?.format!=='pmx')return [];
    const walk=(index,weight,seen)=>{
        if(seen.has(index)||!Number.isFinite(weight))return [];
        const m=data.morphs[index];if(!m)return [];
        if(m.type===8)return m.elements.map(e=>({...e,weight}));
        if(m.type!==0)return [];
        const next=new Set(seen);next.add(index);
        return m.elements.flatMap(e=>walk(e.index,weight*e.ratio,next));
    };
    return data.morphs.map((m,i)=>({name:m.name,operations:walk(i,1,new Set())})).filter(m=>m.operations.length);
}
export function withoutMaterialTargets(data){
    if(data.metadata?.format!=='pmx')return data;
    const hasVertex=(i,seen=new Set())=>{if(seen.has(i))return false;seen=new Set(seen).add(i);let m=data.morphs[i];return m?.type===1||(m?.type===0&&m.elements.some(e=>hasVertex(e.index,seen)));};
    const kept=data.morphs.map((m,i)=>({m,i})).filter(({m,i})=>m.type!==8&&(m.type!==0||hasVertex(i)));
    const indices=new Map(kept.map(({i},n)=>[i,n]));
    const morphs=kept.map(({m})=>m.type===0?{...m,elements:m.elements.filter(e=>indices.has(e.index)).map(e=>({...e,index:indices.get(e.index)}))}:m);
    for(const m of morphs)if(m.type===0)m.elementCount=m.elements.length;
    return {...data,metadata:{...data.metadata,morphCount:morphs.length},morphs};
}
export class PmxMaterialControls{
    constructor(mesh,spec){
        this.mesh=mesh;this.controls=new Map(spec.map(m=>[m.name,m]));this.weights=new Map();this.dirty=false;
        this.materials=Array.isArray(mesh.material)?mesh.material:[mesh.material];
        const rgb=c=>c?.toArray?.().slice(0,3)||[0,0,0];
        this.base=this.materials.map(m=>({opacity:m.opacity,color:rgb(m.diffuse||m.color),specular:rgb(m.specular),ambient:rgb(m.emissive),shininess:m.shininess||0,transparent:m.transparent,depthWrite:m.depthWrite,visible:m.visible,outline:m.userData?.outlineParameters?{...m.userData.outlineParameters,color:[...m.userData.outlineParameters.color]}:null}));
    }
    set(name,value){if(!this.controls.has(name))return false;const n=Math.min(1,Math.max(0,Number.isFinite(value)?value:0));if((this.weights.get(name)||0)!==n){this.weights.set(name,n);this.dirty=true;}return true;}
    apply(){
        if(!this.dirty)return;this.dirty=false;
        const affected=new Set();for(const c of this.controls.values())for(const e of c.operations)if(e.index===-1)this.materials.forEach((_,i)=>affected.add(i));else affected.add(e.index);
        const values=this.base.map(b=>({...b,color:[...b.color],specular:[...b.specular],ambient:[...b.ambient]}));
        const scalar=(old,offset,weight,multiply)=>multiply?old*(1+(offset-1)*weight):old+offset*weight;
        for(const [name,c]of this.controls){let w=this.weights.get(name)||0;if(!w)continue;for(const e of c.operations){let weight=w*e.weight,mul=e.type===0;for(const i of e.index===-1?this.materials.map((_,i)=>i):[e.index]){let v=values[i];if(!v)continue;
            if(e.diffuse){v.opacity=scalar(v.opacity,e.diffuse[3],weight,mul);for(let k=0;k<3;k++)v.color[k]=scalar(v.color[k],e.diffuse[k],weight,mul);}
            for(const [key,source]of [['specular','specular'],['ambient','ambient']])if(e[source])for(let k=0;k<3;k++)v[key][k]=scalar(v[key][k],e[source][k],weight,mul);
            if(Number.isFinite(e.shininess))v.shininess=scalar(v.shininess,e.shininess,weight,mul);
        }}}
        for(const i of affected){const m=this.materials[i],v=values[i],b=this.base[i];if(!m||!v)continue;
            m.opacity=Math.min(1,Math.max(0,v.opacity));(m.diffuse||m.color)?.fromArray(v.color);m.specular?.fromArray(v.specular);m.emissive?.fromArray(v.ambient);m.shininess=Math.max(0,v.shininess);
            // Alpha-zero authored alternatives must become drawable when enabled.
            m.visible=m.opacity>0.0001&&(b.visible!==false||b.opacity<=0.0001);
            const transparent=m.opacity<.999||!!m.map?.transparent;
            if(m.transparent!==transparent){m.transparent=transparent;m.needsUpdate=true;}
            m.depthWrite=m.opacity>=.98?true:b.depthWrite;m.uniformsNeedUpdate=true;
        }
    }
}
export function bindMaterialControls(viewer,mesh){
    const spec=mesh.userData?.pmxMaterialControls||[];viewer.pmxMaterialControls=spec.length?new PmxMaterialControls(mesh,spec):null;
    for(const c of spec)if(!viewer.allMorphNames.includes(c.name))viewer.allMorphNames.push(c.name);
}
