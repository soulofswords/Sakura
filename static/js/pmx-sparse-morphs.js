// Retain sparse facial offsets beyond the GPU's dense morph texture budget.
export function bindSparseMorphs(viewer,mesh){
    const source=mesh.geometry?.userData?.pmxFullMorphs||[];
    const gpu=new Set(Object.keys(mesh.morphTargetDictionary||{}));
    const flatten=(index,weight,result,seen)=>{if(seen.has(index))return;let m=source[index];if(!m)return;
        if(m.type===1)for(const e of m.elements){let d=result.get(e.index)||[0,0,0];for(let k=0;k<3;k++)d[k]+=e.position[k]*weight;result.set(e.index,d);}
        else if(m.type===0){let next=new Set(seen).add(index);for(const e of m.elements)flatten(e.index,weight*e.ratio,result,next);}};
    const controls=new Map();source.forEach((m,i)=>{if(gpu.has(m.name))return;const offsets=new Map();flatten(i,1,offsets,new Set());if(offsets.size)controls.set(m.name,offsets);});
    delete mesh.geometry.userData.pmxFullMorphs;
    viewer.pmxSparseMorphs=null;if(!controls.size)return;
    const geometry=mesh.geometry,position=geometry.attributes.position,base=position.array.slice();
    // Relative GPU displacements combine correctly with sparse CPU eyelids.
    if(!geometry.morphTargetsRelative){for(const attr of geometry.morphAttributes.position||[]){for(let i=0;i<attr.array.length;i++)attr.array[i]-=base[i];attr.needsUpdate=true;}geometry.morphTargetsRelative=true;}
    const indices=[...new Set([...controls.values()].flatMap(m=>[...m.keys()]))].sort((a,b)=>a-b);
    const ranges=[];for(const index of indices){const start=index*3,last=ranges.at(-1);if(last&&start-last.end<=192)last.end=start+3;else ranges.push({start,end:start+3});}
    const weights=new Map();let dirty=false;
    viewer.pmxSparseMorphs={
        set(name,value){if(!controls.has(name))return false;value=Math.max(0,Math.min(1,Number.isFinite(value)?value:0));if((weights.get(name)||0)!==value){weights.set(name,value);dirty=true;}return true;},
        apply(){if(!dirty)return;dirty=false;
            for(const i of indices)for(let k=0;k<3;k++)position.array[i*3+k]=base[i*3+k];
            for(const [name,offsets]of controls){const w=weights.get(name)||0;if(w)for(const [i,d]of offsets)for(let k=0;k<3;k++)position.array[i*3+k]+=d[k]*w;}
            position.clearUpdateRanges();for(const range of ranges)position.addUpdateRange(range.start,range.end-range.start);position.needsUpdate=true;
        },names:[...controls.keys()]
    };
    for(const name of controls.keys())if(!viewer.allMorphNames.includes(name))viewer.allMorphNames.push(name);
    const aliases={A:['あ','A','a'],I:['い','I','i'],U:['う','U','u'],E:['え','E','e'],O:['お','O','o'],Blink:['まばたき','Blink','blink']};
    for(const [key,names]of Object.entries(aliases))if(!viewer.resolvedVowels[key]){let n=names.find(n=>controls.has(n));if(n)viewer.resolvedVowels[key]=n;}
}
