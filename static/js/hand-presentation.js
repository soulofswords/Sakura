import * as THREE from 'three';

// Position-based arm posing: local elbow axes vary between imported rigs.
export function presentHand(viewer,side,blend){
    const bones=viewer.animationBones,upper=bones[side+'Arm']?.bone;
    const lower=bones[side+'Elbow']?.bone,hand=bones[side+'Wrist']?.bone;
    if(!upper?.parent||!lower||!hand?.parent)return false;
    const root=viewer.model;root.updateMatrixWorld(true);
    const position=bone=>bone.getWorldPosition(new THREE.Vector3());
    const shoulder=position(upper),elbow=position(lower),wrist=position(hand);
    const a=shoulder.distanceTo(elbow),b=elbow.distanceTo(wrist),length=a+b;
    if(!Number.isFinite(length)||Math.min(a,b)<1e-5)return false;
    const up=new THREE.Vector3(0,1,0).transformDirection(root.matrixWorld);
    const forward=new THREE.Vector3(0,0,1).transformDirection(root.matrixWorld);
    if(viewer.camera){forward.subVectors(position(viewer.camera),shoulder);forward.addScaledVector(up,-forward.dot(up)).normalize();}
    const right=new THREE.Vector3().crossVectors(up,forward).normalize();
    const center=position(bones.chest?.bone||bones.torso.bone);
    const sign=Math.sign(shoulder.clone().sub(center).dot(right))||(side==='left'?1:-1);
    const target=shoulder.clone().addScaledVector(forward,length*.73)
        .addScaledVector(up,length*.20).addScaledVector(right,sign*length*.17);
    const direction=target.clone().sub(shoulder).normalize(),distance=shoulder.distanceTo(target);
    const along=(a*a-b*b+distance*distance)/(2*distance);
    const bend=right.clone().multiplyScalar(sign*.45).addScaledVector(up,-1);
    bend.addScaledVector(direction,-bend.dot(direction)).normalize();
    const hinge=shoulder.clone().addScaledVector(direction,along)
        .addScaledVector(bend,Math.sqrt(Math.max(0,a*a-along*along)));
    const aim=(joint,end,destination)=>{
        root.updateMatrixWorld(true);
        const origin=position(joint),from=position(end).sub(origin),to=destination.clone().sub(origin);
        if(from.lengthSq()<1e-10||to.lengthSq()<1e-10)return;
        const correction=new THREE.Quaternion().setFromUnitVectors(from.normalize(),to.normalize());
        const world=joint.getWorldQuaternion(new THREE.Quaternion());
        const parent=joint.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
        joint.quaternion.copy(parent.multiply(correction.multiply(world))).normalize();
        joint.updateMatrix();root.updateMatrixWorld(true);
    };
    const oldUpper=upper.quaternion.clone(),oldLower=lower.quaternion.clone(),oldHand=hand.quaternion.clone();
    aim(upper,lower,hinge);aim(lower,hand,target);
    // Imported PMX/VRM hand axes differ. Learn a palm basis from finger roots.
    const fingers=(viewer.conversationFingers||[]).filter(f=>f.side===side&&f.segment===0);
    const index=fingers.find(f=>f.finger===1)?.bone,middle=fingers.find(f=>f.finger===2)?.bone,little=fingers.find(f=>f.finger===4)?.bone;
    if(index&&middle&&little){
        root.updateMatrixWorld(true);
        const localUp=hand.worldToLocal(position(middle)).normalize();
        const across=hand.worldToLocal(position(index)).sub(hand.worldToLocal(position(little))).normalize();
        const normal=new THREE.Vector3().crossVectors(across,localUp).normalize().multiplyScalar(side==='left'?1:-1);
        const x=new THREE.Vector3().crossVectors(localUp,normal).normalize();
        if(normal.lengthSq()>.5&&x.lengthSq()>.5){
            const source=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,localUp,normal));
            const desiredX=new THREE.Vector3().crossVectors(up,forward).normalize();
            const desired=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(desiredX,up,forward));
            hand.quaternion.copy(hand.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(desired).multiply(source.invert()));
        }
    }
    const solvedUpper=upper.quaternion.clone(),solvedLower=lower.quaternion.clone(),solvedHand=hand.quaternion.clone();
    upper.quaternion.copy(oldUpper).slerp(solvedUpper,blend);lower.quaternion.copy(oldLower).slerp(solvedLower,blend);
    hand.quaternion.copy(oldHand).slerp(solvedHand,blend);root.updateMatrixWorld(true);
    return true;
}
