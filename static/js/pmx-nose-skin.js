import * as THREE from 'three';

// These exports use a separate, translucent NOSE LIGHT surface to complete
// the nose geometry. Replace that surface's finish, not the geometry itself.
export function repairNoseSkin(root){
    let repaired=0;
    root.traverse(mesh=>{
        const materials=Array.isArray(mesh.material)?mesh.material:[],geometry=mesh.geometry;
        const faceIndex=materials.findIndex(m=>/^face$/i.test(m?.name||'')),face=materials[faceIndex];
        if(!face?.map||!geometry?.index||!geometry.attributes?.uv||!geometry.attributes.position)return;
        const image=face.map.image,width=image?.naturalWidth||image?.width,height=image?.naturalHeight||image?.height;
        if(!width||!height||width*height>16777216)return;
        const noses=materials.map((m,i)=>({m,i})).filter(({m})=>/^nose[ _-]*light$/i.test(m?.name||'')&&!m.userData?.sakuraNoseSkin);
        if(!noses.length)return;
        const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
        const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0);
        const pixels=context.getImageData(0,0,width,height).data,positions=geometry.attributes.position,uv=geometry.attributes.uv;
        const faceGroup=geometry.groups.find(g=>g.materialIndex===faceIndex);if(!faceGroup)return;
        for(const {m,i}of noses){
            const group=geometry.groups.find(g=>g.materialIndex===i);if(!group?.count)continue;
            const center=new THREE.Vector3(),point=new THREE.Vector3();
            for(let j=group.start;j<group.start+group.count;j++)center.add(point.fromBufferAttribute(positions,geometry.index.getX(j)));center.divideScalar(group.count);
            const nearest=[];const seen=new Set();
            for(let j=faceGroup.start;j<faceGroup.start+faceGroup.count;j++){const index=geometry.index.getX(j);if(seen.has(index))continue;seen.add(index);point.fromBufferAttribute(positions,index);nearest.push({index,distance:point.distanceToSquared(center)});}
            nearest.sort((a,b)=>a.distance-b.distance);
            const colors=[];
            for(const candidate of nearest.slice(0,80)){
                const x=THREE.MathUtils.clamp(Math.round(uv.getX(candidate.index)*(width-1)),0,width-1),y=THREE.MathUtils.clamp(Math.round((face.map.flipY?1-uv.getY(candidate.index):uv.getY(candidate.index))*(height-1)),0,height-1),offset=(y*width+x)*4;
                const [r,g,b,a]=pixels.slice(offset,offset+4);
                if(a>240&&r>90&&g>70&&r>=g*.9&&r>=b*.95)colors.push([r,g,b]);
                if(colors.length>=12)break;
            }
            if(!colors.length)continue;
            const rgba=new Uint8Array([0,0,0,255]);for(let c=0;c<3;c++)rgba[c]=Math.round(colors.reduce((sum,color)=>sum+color[c],0)/colors.length);
            const skinCanvas=document.createElement('canvas');skinCanvas.width=skinCanvas.height=1;
            const skinContext=skinCanvas.getContext('2d'),skinPixel=skinContext.createImageData(1,1);skinPixel.data.set(rgba);skinContext.putImageData(skinPixel,0,0);
            const texture=new THREE.CanvasTexture(skinCanvas);texture.colorSpace=face.map.colorSpace;texture.needsUpdate=true;
            const replacement=face.clone();replacement.name=m.name;replacement.map=texture;replacement.emissiveMap=texture;replacement.opacity=1;replacement.transparent=false;replacement.alphaTest=0;replacement.depthWrite=true;
            replacement.userData={...replacement.userData,sakuraNoseSkin:true};replacement.needsUpdate=true;materials[i]=replacement;repaired++;
            m.dispose();
        }
    });return repaired;
}
