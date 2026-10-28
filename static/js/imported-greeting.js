import * as THREE from 'three';
import AvatarRetarget from './avatar-retarget.js?v=irina-greeting113';
let cached;
export default class ImportedGreeting {
    constructor(viewer){this.viewer=viewer;this.data=null;}
    async load(){
        if(!cached)cached=fetch('/static/assets/animations/hand-raising.json?v=fbx89').then(async response=>{
            if(!response.ok)throw Error('Hand Raising animation could not load');
            const data=await response.json();
            if(data.version!==1||!(data.duration>0)||!data.frames?.length)throw Error('Invalid Hand Raising animation');
            return data;
        }).catch(error=>{cached=null;throw error;});
        this.data=await cached;return this.data;
    }
    begin(){
        const v=this.viewer;if(!this.data||!v.model||v.live2d||(v.userTracking||v.vtuberTrackingMode)&&!v.companionTracking)return null;
        const entries=Object.entries(v.animationBones).filter(([key])=>Object.hasOwn(this.data.frames[0].rotations,key))
            .map(([key,e])=>({key,bone:e.bone,rest:new THREE.Quaternion().setFromEuler(e.rest)}));
        for(const f of v.conversationFingers||[]){const key=f.side+'Finger'+f.finger+'_'+f.segment;
            if(Object.hasOwn(this.data.frames[0].rotations,key))entries.push({key,bone:f.bone,rest:new THREE.Quaternion().setFromEuler(f.rest)});}
        const irina=!!v.model.getObjectByName('Breast_L_C1')&&!!v.model.getObjectByName('Bip001 L Finger0');
        const seen=new Set(),mapped=entries.filter(e=>{if(irina&&e.key.endsWith('Shoulder'))return false;if(seen.has(e.bone))return false;seen.add(e.bone);return true;});
        const all=new Map();for(const e of Object.values(v.animationBones))all.set(e.bone,new THREE.Quaternion().setFromEuler(e.rest));
        for(const f of v.conversationFingers||[])all.set(f.bone,new THREE.Quaternion().setFromEuler(f.rest));
        const before=new Map([...all].map(([bone])=>[bone,bone.quaternion.clone()]));
        for(const [bone,rest]of all)bone.quaternion.copy(rest);
        v.model.updateMatrixWorld(true);
        const pos=b=>b.getWorldPosition(new THREE.Vector3()),b=v.animationBones;
        const x=pos(b.leftArm.bone).sub(pos(b.rightArm.bone)).normalize();
        const y=pos((b.neck||b.head||b.chest).bone).sub(pos(b.torso.bone));y.addScaledVector(x,-y.dot(x)).normalize();
        const z=new THREE.Vector3().crossVectors(x,y).normalize();
        const body=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z));
        const targets=Object.fromEntries(mapped.map(e=>[e.key,e.bone]));
        const endpoints={};
        for(const side of ['left','right']){
            endpoints[side+'Shoulder']=targets[side+'Arm'];endpoints[side+'Arm']=targets[side+'Elbow'];
            endpoints[side+'Elbow']=targets[side+'Wrist'];endpoints[side+'Wrist']=targets[side+'Finger2_0'];
            for(let f=0;f<5;f++)for(let segment=0;segment<3;segment++)endpoints[side+'Finger'+f+'_'+segment]=targets[side+'Finger'+f+'_'+(segment+1)];
        }
        for(const e of mapped){
            e.bind=e.bone.getWorldQuaternion(new THREE.Quaternion());e.start=before.get(e.bone).clone();
            const direction=this.data.bindDirections?.[e.key],end=endpoints[e.key];
            if(direction&&end){
                const from=pos(end).sub(pos(e.bone)),to=new THREE.Vector3().fromArray(direction).applyQuaternion(body);
                if(from.lengthSq()>1e-10&&to.lengthSq()>.5)e.bind.premultiply(new THREE.Quaternion().setFromUnitVectors(from.normalize(),to.normalize()));
            }
        }
        const depth=bone=>{let n=0;while(bone.parent){n++;bone=bone.parent;}return n;};mapped.sort((a,b)=>depth(a.bone)-depth(b.bone));
        for(const [bone,q]of before)bone.quaternion.copy(q);
        v.model.updateMatrixWorld(true);
        if(irina)this.armSolver=new AvatarRetarget(v);
        return {root:v.model,entries:mapped,body,inverse:body.clone().invert(),irina,
            rightHandStart:irina?pos(b.rightWrist.bone):null};
    }
    apply(state,time,blend,stopping){
        if(!state||state.root!==this.viewer.model)return;
        const bones=this.viewer.animationBones;
        if(state.irina)for(const side of ['left','right']){const e=bones[side+'Shoulder'];if(e)e.bone.quaternion.setFromEuler(e.rest);}
        const data=this.data,frames=data.frames,index=Math.min(frames.length-2,Math.floor(Math.min(time,data.duration)*data.fps));
        const a=frames[Math.max(0,index)],b=frames[Math.min(frames.length-1,index+1)];
        const mix=THREE.MathUtils.clamp((time-a.time)/Math.max(1e-6,b.time-a.time),0,1);
        const q=new THREE.Quaternion(),next=new THREE.Quaternion(),parent=new THREE.Quaternion();
        for(const e of state.entries){
            q.fromArray(a.rotations[e.key]);next.fromArray(b.rotations[e.key]);q.slerp(next,mix).normalize();
            q.premultiply(state.body).multiply(state.inverse).multiply(e.bind);
            e.bone.parent.getWorldQuaternion(parent).invert();q.premultiply(parent).normalize();
            e.bone.quaternion.copy(e.start).slerp(q,blend);
            e.bone.updateMatrix();e.bone.updateWorldMatrix(false,true);
        }
        if(state.irina){
            // The FBX greeting lifts its collarbone and keeps the elbow almost
            // straight. On Irina this stretches chest skin and raises the long
            // sleeve over her face. Retain the clip's timing/fingers, but solve
            // a bent-elbow wave beside the shoulder with a stationary clavicle.
            const upper=bones.rightArm.bone,elbow=bones.rightElbow.bone,hand=bones.rightWrist.bone;
            const pos=bone=>bone.getWorldPosition(new THREE.Vector3());
            const origin=pos(upper),length=origin.distanceTo(pos(elbow))+pos(elbow).distanceTo(pos(hand));
            const wristWorld=hand.getWorldQuaternion(new THREE.Quaternion());
            const offset=pos(hand).sub(origin).applyQuaternion(state.inverse);
            offset.x=Math.min(offset.x,-length*.62);
            offset.y=THREE.MathUtils.clamp(offset.y,-length*.85,length*.38);
            offset.z=THREE.MathUtils.clamp(offset.z,-length*.20,length*.32);
            const target=offset.applyQuaternion(state.body).add(origin);
            target.lerpVectors(state.rightHandStart,target,blend);
            const pole=new THREE.Vector3(-length*.85,-length*.22,-length*.15).applyQuaternion(state.body).add(origin);
            this.armSolver._solveIridaArm('right',target,1,pole,1);
            const parent=hand.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
            hand.quaternion.copy(parent.multiply(wristWorld));
            hand.updateMatrix();hand.updateWorldMatrix(false,true);
        }
    }
    restore(state){for(const e of state?.entries||[])e.bone.quaternion.copy(e.start);}
}
