import * as THREE from 'three';

// Condition the camera pose once per sample, before either Live2D or 3D uses it.
// Quaternion interpolation avoids Euler wrap jumps; isolated detector spikes
// cannot snap the head, but a sustained real turn is accepted on the next frame.
export default class HeadPoseFilter {
    constructor(){this.reset();}
    reset(){this.rotation=null;this.time=null;this.pending=null;}
    update(face,timestamp,distanceAssist){
        if(!face?.matrix?.length||!face.landmarks?.length)return face;
        if(face.matrix.length!==16||!Array.from(face.matrix).every(Number.isFinite))return {...face,matrix:null};
        const matrix=new THREE.Matrix4().fromArray(face.matrix),rotationMatrix=new THREE.Matrix4().extractRotation(matrix);
        const target=new THREE.Quaternion().setFromRotationMatrix(rotationMatrix).normalize();
        if(!Number.isFinite(target.x+target.y+target.z+target.w))return {...face,matrix:null};
        if(!this.rotation){this.rotation=target.clone();this.time=timestamp;return face;}
        const dt=Math.max(.001,Math.min(.2,(timestamp-this.time)/1000));this.time=timestamp;
        const jump=this.rotation.angleTo(target),spike=jump>Math.max(.5,dt*7);
        if(spike&&(!this.pending||this.pending.angleTo(target)>.12)){this.pending=target.clone();return {...face,matrix:this.matrix(matrix)};}
        this.pending=null;
        const distant=!!distanceAssist?.faceZoomed;
        const alpha=1-Math.exp(-dt/(distant ? .11 : .055));
        const limited=Math.min(alpha,jump>1e-6?dt*4/jump:1);
        if(jump>(distant ? .008 : .003))this.rotation.slerp(target,limited).normalize();
        return {...face,matrix:this.matrix(matrix)};
    }
    matrix(original){
        const result=new THREE.Matrix4().makeRotationFromQuaternion(this.rotation);
        result.setPosition(new THREE.Vector3().setFromMatrixPosition(original));return result.toArray();
    }
}
