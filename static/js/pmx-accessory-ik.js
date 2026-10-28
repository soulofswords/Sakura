import {CCDIKSolver} from 'three/addons/animation/CCDIKSolver.js';

// Some PMX coats use a separate sleeve chain whose IK target follows the
// animated upper arm. Leaving that authored IK idle tears the sleeve open.
// Solve only auxiliary chains attached to driven arms; never leg/body IK.
export function updateAccessoryIK(viewer){
    const mesh=viewer.model;
    if(!mesh?.skeleton||viewer.vrm||viewer.live2d)return;
    if(viewer._accessoryIKModel!==mesh){
        viewer._accessoryIKModel=mesh;
        const bones=mesh.skeleton.bones,driven=new Set(Object.values(viewer.animationBones||{}).map(x=>x.bone));
        const arms=new Set(['leftArm','rightArm','leftElbow','rightElbow'].map(k=>viewer.animationBones?.[k]?.bone).filter(Boolean));
        const iks=(mesh.geometry?.userData?.MMD?.iks||[]).filter(ik=>{
            if(!ik.links?.length||ik.links.length>4||ik.links.some(link=>driven.has(bones[link.index])))return false;
            let target=bones[ik.target];
            for(let i=0;target&&i<12;i++,target=target.parent)if(arms.has(target))return true;
            return false;
        }).map(ik=>({...ik,iteration:Math.min(10,ik.iteration||10)}));
        viewer._accessoryIK=iks.length?new CCDIKSolver(mesh,iks):null;
    }
    viewer._accessoryIK?.update();
}
