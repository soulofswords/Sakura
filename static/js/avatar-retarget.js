import * as THREE from 'three';
const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : 0));
function faceAperture(points, corners, pairs) {
    const distance = (a,b) => {
        const p=points?.[a], q=points?.[b];
        return p && q && [p.x,p.y,q.x,q.y].every(Number.isFinite)
            ? Math.hypot((p.x-q.x)*4/3,p.y-q.y) : null;
    };
    const width=distance(...corners), gaps=pairs.map(pair=>distance(...pair));
    if (!(width>1e-5) || gaps.some(value=>value===null)) return null;
    return gaps.reduce((sum,value)=>sum+value,0)/gaps.length/width;
}
function eyeAperture(points, left) {
    return left ? faceAperture(points,[362,263],[[385,380],[386,374],[387,373]])
        : faceAperture(points,[33,133],[[158,153],[159,145],[160,144]]);
}
function apertureBlink(ratio, neutral) {
    if (ratio===null) return 0;
    const closure=clamp((1-ratio/neutral-.15)/.65);
    return closure*closure*(3-2*closure);
}
function glassesBlink(score,ratio,neutral,gain){
    if(ratio===null)return faceBlinkWeight(score*gain);
    // Glasses reflections can raise blink scores while the eyelid landmarks
    // remain open. Prefer the calibrated opening and admit score evidence
    // only after those landmarks also show real closure.
    const closure=apertureBlink(ratio,neutral);
    const evidence=clamp((.85-ratio/neutral)/.45);
    return clamp(Math.max(closure,faceBlinkWeight(score*gain)*evidence));
}
export function faceBlinkWeight(score) {
    // MediaPipe scores are often conservative for quick/partial blinks. Map
    // the useful range to a decisive closure while rejecting low-level noise.
    const t = clamp((clamp(score) - 0.12) / 0.48);
    return t * t * (3 - 2 * t);
}
export function jointCurl(points, a, b, c) {
    if (!points?.[a] || !points?.[b] || !points?.[c]) return 0;
    const left = new THREE.Vector3(points[a].x-points[b].x, points[a].y-points[b].y, points[a].z-points[b].z);
    const right = new THREE.Vector3(points[c].x-points[b].x, points[c].y-points[b].y, points[c].z-points[b].z);
    return clamp(Math.PI - left.angleTo(right), 0, 1.7);
}
export function fingerJointCurl(points, finger, segment) {
    const base = finger * 4 + 1;
    const joint = base + segment;
    // Wrist → MCP → PIP → DIP → fingertip. Each avatar joint follows its
    // corresponding webcam joint instead of reusing the PIP angle for DIP.
    const previous = segment === 0 ? 0 : joint - 1;
    if (finger>0 && segment===0 && points?.[5] && points?.[17] && points?.[0] && points?.[joint+1]) {
        const vector=(a,b)=>new THREE.Vector3(points[a].x-points[b].x,points[a].y-points[b].y,points[a].z-points[b].z);
        const normal=vector(5,0).cross(vector(17,0));
        const forward=vector(joint,0).normalize(), distal=vector(joint+1,joint);
        const hinge=forward.clone().cross(normal).normalize();
        if (normal.lengthSq()>1e-10 && hinge.lengthSq()>1e-10) {
            // Remove sideways spread from the flexion plane at the knuckle.
            distal.addScaledVector(hinge,-distal.dot(hinge));
            return distal.lengthSq()>1e-10 ? clamp(forward.angleTo(distal),0,1.7) : 0;
        }
    }
    return jointCurl(points, previous, joint, joint + 1);
}
export default class AvatarRetarget {
    constructor(viewer) {
        this.viewer = viewer;
        this.neutral = new THREE.Euler();
        this.mouthTrackingEnabled = viewer.trackingMouthEnabled !== false;
        this.mouthMorphs = new Set(['A','I','U','E','O']);
        this.bind();
    }
    setMouthTracking(enabled) {
        this.mouthTrackingEnabled = Boolean(enabled);
        if (!this.mouthTrackingEnabled) {
            for (const name of this.mouthMorphs) {
                this.weights[name] = 0;
                this.viewer.setMorph(name, 0);
            }
        }
    }
    bind() {
        this.root = this.viewer.model;
        this.fingers = [];
        if (!this.root) return;
        const names = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
        const japanese = ['親指', '人指', '中指', '薬指', '小指'];
        const segments = ['Proximal', 'Intermediate', 'Distal'];
        const fullwidth = ['０','１','２','３'];
        for (const side of ['left','right']) for (let finger=0; finger<5; finger++) for(let segment=0;segment<3;segment++) {
            const vrmName = side+names[finger]+(finger===0 ? ['Metacarpal','Proximal','Distal'][segment] : segments[segment]);
            let bone = this.viewer.vrm?.humanoid?.getNormalizedBoneNode(vrmName);
            if (!bone) this.root.traverse(child => {
                const index = finger===0 ? segment : segment+1;
                const aliases = [(side==='left'?'左':'右')+japanese[finger]+index,
                    (side==='left'?'左':'右')+japanese[finger]+fullwidth[index],
                    (side==='left'?'Left':'Right')+names[finger]+(segment+1)];
                if (child.isBone && aliases.includes(child.name)) bone = child;
            });
            if (bone) this.fingers.push({side,finger,segment,bone,rest:bone.quaternion.clone()});
        }
        this.height = Math.max(1, new THREE.Box3().setFromObject(this.root).getSize(new THREE.Vector3()).y);
        this.root.updateMatrixWorld(true);
        const armBones=this.viewer.animationBones;
        for(const side of ['left','right']) {
            const wrist=armBones[side+'Wrist']?.bone;
            const index=this.fingers.find(f=>f.side===side && f.finger===1 && f.segment===0)?.bone;
            const little=this.fingers.find(f=>f.side===side && f.finger===4 && f.segment===0)?.bone;
            const normal=wrist && index && little
                ? index.getWorldPosition(new THREE.Vector3()).sub(wrist.getWorldPosition(new THREE.Vector3()))
                    .cross(little.getWorldPosition(new THREE.Vector3()).sub(wrist.getWorldPosition(new THREE.Vector3()))).normalize().multiplyScalar(side==='left'?-1:1)
                : null;
            const middle=this.fingers.find(f=>f.side===side && f.finger===2 && f.segment===0)?.bone;
            const middleChild=middle?.children.find(b=>b.isBone && b.position.lengthSq()>1e-8);
            const reference=middleChild ? middleChild.getWorldPosition(new THREE.Vector3()).sub(middle.getWorldPosition(new THREE.Vector3())).normalize() : null;
            for(const entry of this.fingers.filter(f=>f.side===side)) {
                entry.bendAxis=new THREE.Vector3(0,0,side==='left'?-1:1);
                const child=entry.bone.children.find(b=>b.isBone && b.position.lengthSq()>1e-8);
                if(normal?.lengthSq()>1e-8 && (child || entry.bone.parent?.isBone)) {
                    const direction=child
                        ? child.getWorldPosition(new THREE.Vector3()).sub(entry.bone.getWorldPosition(new THREE.Vector3()))
                        : entry.bone.getWorldPosition(new THREE.Vector3()).sub(entry.bone.parent.getWorldPosition(new THREE.Vector3()));
                    if(entry.segment===0 && entry.finger>0 && reference) {
                        entry.spreadAxis=normal.clone().applyQuaternion(entry.bone.getWorldQuaternion(new THREE.Quaternion()).invert());
                        entry.restSpread=Math.atan2(normal.dot(reference.clone().cross(direction)),reference.dot(direction));
                    }
                    const axis=direction.cross(normal).normalize();
                    if(axis.lengthSq()>1e-8)entry.bendAxis.copy(axis).applyQuaternion(entry.bone.getWorldQuaternion(new THREE.Quaternion()).invert());
                }
            }
        }
        this.shoulderWidth=armBones.leftArm && armBones.rightArm
            ? armBones.leftArm.bone.getWorldPosition(new THREE.Vector3()).distanceTo(armBones.rightArm.bone.getWorldPosition(new THREE.Vector3())) : this.height*.2;
        this.morphs = new Set();
        this.weights = {};
        this.palms = {};
        this.calibrated = false;
        this.faceNeutral = {leftEye:.28,rightEye:.28,mouth:.025};
        this.handPresence = {};
        this.handTargets = {};
    }
    rotation(matrix) {
        if (!matrix?.length) return new THREE.Euler();
        // MediaPipe's Matrix data is column-major, like Three.js Matrix4.
        return new THREE.Euler().setFromRotationMatrix(new THREE.Matrix4().fromArray(matrix), 'XYZ');
    }
    calibrate(sample) {
        if (sample?.face?.matrix && sample.face.landmarks?.length) {
            this.neutral.copy(this.rotation(sample.face.matrix)); this.calibrated = true;
        }
        const points=sample?.face?.landmarks;
        const scores=Object.fromEntries((sample?.face?.blendshapes || []).map(b=>[b.categoryName,b.score]));
        for (const [key,left] of [['leftEye',true],['rightEye',false]]) {
            const ratio=eyeAperture(points,left);
            const glasses=!!this.viewer.trackingOptions?.glasses;
            if (ratio!==null && ratio>(glasses?.08:.14) && (glasses||(scores[left?'eyeBlinkLeft':'eyeBlinkRight']||0)<.3)) this.faceNeutral[key]=clamp(ratio,glasses?.08:.18,.4);
        }
        const mouth=faceAperture(points,[61,291],[[13,14]]);
        if (mouth!==null && (scores.jawOpen||0)<.2) this.faceNeutral.mouth=clamp(mouth,0,.12);
        this.palms={};
    }
    reset() {
        for (const entry of this.fingers) entry.bone.quaternion.copy(entry.rest);
        for (const name of this.morphs || []) this.viewer.setMorph(name, 0);
        for (const entry of Object.values(this.viewer.animationBones)) entry.bone.rotation.copy(this.viewer.vtuberTrackingMode?(entry.trackingRest||entry.rest):entry.rest);
        this.handPresence = {};
        this.palms = {};
        this.handTargets = {};
    }
    _visibleHand(hand) {
        const points=hand?.landmarks;
        const confidence=hand?.confidence ?? 1;
        if (!Array.isArray(points) || points.length!==21 || !Number.isFinite(confidence) || confidence<.75) return false;
        if (!points.every(p=>p && [p.x,p.y,p.z].every(Number.isFinite) && p.x>=0 && p.x<=1 && p.y>=0 && p.y<=1)) return false;
        const palmWidth=Math.hypot(points[5].x-points[17].x,points[5].y-points[17].y);
        return palmWidth>.008 && palmWidth<.5;
    }
    _confirmedHand(side, candidate, sample, enabled) {
        const stamp=sample?.timestamp ?? sample?.receivedAt;
        const recent=sample && performance.now()-sample.receivedAt<200;
        if (!enabled || !recent || !this._visibleHand(candidate) || !Number.isFinite(stamp)) {
            this.handPresence[side]=null;
            return null;
        }
        let state=this.handPresence[side];
        if (!state || stamp<state.stamp || stamp-state.stamp>200) state={stamp,count:1};
        else if (stamp!==state.stamp) {state.stamp=stamp;state.count++;}
        this.handPresence[side]=state;
        return state.count>=2 ? candidate : null;
    }
    apply(sample, delta) {
        if (this.root !== this.viewer.model) this.bind();
        if (!this.root) return;
        const options = this.viewer.trackingOptions || {};
        const response = .02 + clamp(options.smoothing ?? .25) * .2;
        const alpha = 1-Math.exp(-Math.min(delta,.1)/response);
        const bones = this.viewer.animationBones;
        const fresh = sample && performance.now()-sample.receivedAt < 600;
        const face = fresh ? sample.face : null;
        // The first detected face is the neutral pose, rather than assuming
        // the camera's transformation matrix has zero Euler rotation.
        if (!this.calibrated && face?.landmarks?.length) this.calibrate(sample);
        const scores = Object.fromEntries((face?.blendshapes || []).map(b=>[b.categoryName,clamp(b.score)]));
        const morph = (name,value, responseSeconds=.07) => {
            if(this.viewer.mouthOptions?.source==='both'&&['A','I','U','E','O'].includes(name))value=Math.max(value,this.viewer.microphoneMouthWeights?.[name]||0);
            if (!name) return;
            this.morphs.add(name);
            if (/mouth|jaw|lip|viseme|^(A|I|U|E|O)$/i.test(name)) this.mouthMorphs.add(name);
            const previous=this.weights[name]||0;
            const responseAlpha = responseSeconds === .07 ? alpha
                : 1-Math.exp(-Math.min(delta,.1)/responseSeconds);
            this.weights[name]=previous+(value-previous)*responseAlpha;
            this.viewer.setMorph(name,this.weights[name]);
        };
        const alias = (...names) => names.find(n=>this.viewer.morphMap[n] || this.viewer.vrm?.expressionManager?.getExpression(n));
        for (const [name,value] of Object.entries(scores)) {
            if (name === 'eyeBlinkLeft' || name === 'eyeBlinkRight') continue;
            if (!this.mouthTrackingEnabled && /mouth|jaw|lip|viseme/i.test(name)) continue;
            const actual = alias(name);
            if (actual) morph(actual,value);
        }
        const blinkLeft=alias('blinkLeft','ウィンク','ウィンク２','winkLeft');
        const blinkRight=alias('blinkRight','ウィンク右','winkRight');
        const blinkGain = clamp(options.blinkGain ?? 1, .5, 2);
        let leftBlink=Math.max(faceBlinkWeight((scores.eyeBlinkLeft || 0)*blinkGain),
            apertureBlink(eyeAperture(face?.landmarks,true),this.faceNeutral.leftEye)*blinkGain);
        let rightBlink=Math.max(faceBlinkWeight((scores.eyeBlinkRight || 0)*blinkGain),
            apertureBlink(eyeAperture(face?.landmarks,false),this.faceNeutral.rightEye)*blinkGain);
        if(options.glasses){
            leftBlink=glassesBlink(scores.eyeBlinkLeft||0,eyeAperture(face?.landmarks,true),this.faceNeutral.leftEye,blinkGain);
            rightBlink=glassesBlink(scores.eyeBlinkRight||0,eyeAperture(face?.landmarks,false),this.faceNeutral.rightEye,blinkGain);
        }
        leftBlink=clamp(leftBlink); rightBlink=clamp(rightBlink);
        if (options.linkBlinks) leftBlink = rightBlink = Math.max(leftBlink, rightBlink);
        if (blinkLeft && blinkRight) {
            morph(blinkLeft,leftBlink,leftBlink>(this.weights[blinkLeft]||0)?.018:.035);
            morph(blinkRight,rightBlink,rightBlink>(this.weights[blinkRight]||0)?.018:.035);
        } else {
            const blink=Math.max(leftBlink,rightBlink);
            morph('Blink',blink,blink>(this.weights.Blink||0)?.018:.035);
        }
        const mouthGap=faceAperture(face?.landmarks,[61,291],[[13,14]]);
        const mouthOpen=mouthGap===null ? 0 : clamp((mouthGap-this.faceNeutral.mouth-.015)/.35);
        if (this.mouthTrackingEnabled) {
            morph('A',Math.max(clamp((scores.jawOpen||0)*1.6),mouthOpen),.035);
            morph(alias('mouthSmile','にこり','笑い','happy'),Math.max(scores.mouthSmileLeft||0,scores.mouthSmileRight||0));
            morph('U',Math.max(scores.mouthPucker||0,scores.mouthFunnel||0));
        }
        morph(alias('browInnerUp','困る','sad'),scores.browInnerUp||0);
        morph(alias('browDownLeft','真面目'),Math.max(scores.browDownLeft||0,scores.browDownRight||0));
        if (!face?.landmarks?.length) for (const name of this.morphs) morph(name,0);
        const rotation=face?.matrix ? this.rotation(face.matrix) : this.neutral;
        const sign=this.viewer.userTrackingMirror===false ? -1 : 1;
        const rotate = (key,x,y,z) => {
            const entry=bones[key]; if(!entry) return;
            const target=new THREE.Quaternion().setFromEuler(new THREE.Euler(entry.rest.x+x,entry.rest.y+y,entry.rest.z+z,entry.rest.order));
            entry.bone.quaternion.slerp(target,alpha);
        };
        const range = clamp(options.range ?? 1, 0, 2);
        rotate('head',clamp((rotation.x-this.neutral.x)*range,-.7,.7),clamp((rotation.y-this.neutral.y)*sign*range,-.9,.9),clamp((rotation.z-this.neutral.z)*sign*range,-.6,.6));
        const gazeX=((scores.eyeLookInLeft||0)+(scores.eyeLookOutRight||0)-(scores.eyeLookOutLeft||0)-(scores.eyeLookInRight||0))*.2;
        const gazeY=((scores.eyeLookDownLeft||0)+(scores.eyeLookDownRight||0)-(scores.eyeLookUpLeft||0)-(scores.eyeLookUpRight||0))*.15;
        const gaze = clamp(options.gaze ?? 1, 0, 2);
        if (!this.viewer.eyeTrackingEnabled) {
            rotate('leftEye',gazeY*gaze,gazeX*gaze,0); rotate('rightEye',gazeY*gaze,gazeX*gaze,0);
        }
        const bodyTracking=fresh && sample.handTrackingEnabled !== false;
        const hands=bodyTracking ? sample.hands || [] : [];
        const pose=bodyTracking ? sample.pose : null;
        const posePoints=pose?.landmarks || [];
        const poseWorld=pose?.world || [];
        const poseShouldersValid=[11,12].every(i=>posePoints[i] && (posePoints[i].visibility ?? 1) > .35);
        let poseScale=this.height;
        let poseDepthScale=this.height;
        if(poseShouldersValid && bones.leftArm && bones.rightArm) {
            this.root.updateMatrixWorld(true);
            const avatarWidth=this.shoulderWidth;
            const cameraWidth=Math.abs(posePoints[11].x-posePoints[12].x);
            if(avatarWidth>1e-4 && cameraWidth>1e-4) poseScale=avatarWidth/cameraWidth;
            const worldWidth=poseWorld[11] && poseWorld[12] ? new THREE.Vector3(poseWorld[11].x-poseWorld[12].x,poseWorld[11].y-poseWorld[12].y,poseWorld[11].z-poseWorld[12].z).length() : 0;
            if(avatarWidth>1e-4 && worldWidth>1e-4) poseDepthScale=avatarWidth/worldWidth;
        }
        const assignedHands=new Map();
        for (const candidate of hands) {
            let side=candidate.side?.toLowerCase();
            if (this._visibleHand(candidate) && poseShouldersValid) {
                const wrist=candidate.landmarks[0];
                const distances=[15,16].map(i=>posePoints[i] && (posePoints[i].visibility ?? 1)>.6
                    ? Math.hypot(wrist.x-posePoints[i].x,wrist.y-posePoints[i].y) : Infinity);
                if (Math.min(...distances)<.2 && Math.abs(distances[0]-distances[1])>.04) side=distances[0]<distances[1]?'left':'right';
            }
            if (!assignedHands.has(side) || (candidate.confidence ?? 1)>(assignedHands.get(side).confidence ?? 1)) assignedHands.set(side,candidate);
        }
        for(const side of ['left','right']) {
            const hand=this._confirmedHand(side,assignedHands.get(side),sample,bodyTracking);
            const left=side==='left';
            const indices=left ? [11,13,15] : [12,14,16];
            const poseArmValid=!!hand && poseShouldersValid && indices.every(i=>posePoints[i]
                && (posePoints[i].visibility ?? 1) > .6 && [posePoints[i].x,posePoints[i].y,posePoints[i].z].every(Number.isFinite))
                && Math.hypot(hand.landmarks[0].x-posePoints[indices[2]].x,hand.landmarks[0].y-posePoints[indices[2]].y)<.2;
            if (hand) {
                rotate(side+'Wrist',0,0,0);
            } else {
                // Let the tracked upper body return smoothly to its authored pose.
                for (const key of [side+'Shoulder',side+'Arm',side+'Elbow',side+'Wrist']) {
                    const entry=bones[key];
                    if (entry?.rest) entry.bone.quaternion.slerp(new THREE.Quaternion().setFromEuler(entry.trackingRest||entry.rest),alpha);
                }
                this.palms[side]=null;
                this.handTargets[side]=null;
            }
            if(poseArmValid && indices.every(i=>poseWorld[i] && [poseWorld[i].x,poseWorld[i].y,poseWorld[i].z].every(Number.isFinite)) && bones[side+'Wrist']) {
                this.root.updateMatrixWorld(true);
                const shoulder=bones[side+'Shoulder']?.bone || bones[side+'Arm']?.bone;
                if(shoulder) {
                    const origin=shoulder.getWorldPosition(new THREE.Vector3());
                    const point=i=>{
                        const image=i===indices[2] ? hand.landmarks[0] : posePoints[i], world=poseWorld[i];
                        const cameraX=(image.x-posePoints[indices[0]].x)*sign;
                        const cameraY=posePoints[indices[0]].y-image.y;
                        // MediaPipe Z decreases toward the webcam. The
                        // front-facing avatar reaches toward positive Z.
                        const depth=poseWorld[indices[0]].z-world.z;
                        return origin.clone().add(new THREE.Vector3(cameraX*poseScale,cameraY*poseScale,depth*poseDepthScale));
                    };
                    this.solveArm(side,point(indices[2]),alpha,point(indices[1]));
                }
            } else if(hand?.landmarks?.length && face?.landmarks?.[1] && bones.head) {
                const wrist=hand.landmarks[0],nose=face.landmarks[1];
                const target=bones.head.bone.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(
                    (wrist.x-nose.x)*this.height*sign,(nose.y-wrist.y)*this.height,this.height*.12));
                this.solveArm(side,target,alpha);
            }
            if(hand?.world?.length===21 && hand.world.every(p=>p && [p.x,p.y,p.z].every(Number.isFinite)) && bones[side+'Wrist']) {
                const point=i=>new THREE.Vector3(-hand.world[i].x,-hand.world[i].y,hand.world[i].z);
                const x=point(5).sub(point(17)).normalize();
                const y=point(9).sub(point(0)).normalize();
                const z=new THREE.Vector3().crossVectors(x,y).normalize();
                y.crossVectors(z,x).normalize();
                const palm=new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x,y,z));
                if(!this.palms[side]) this.palms[side]=palm.clone();
                const motion=this.palms[side].clone().invert().multiply(palm);
                const entry=bones[side+'Wrist'];
                const parent=entry.bone.parent.getWorldQuaternion(new THREE.Quaternion());
                const localMotion=parent.clone().invert().multiply(motion).multiply(parent);
                const target=localMotion.multiply(new THREE.Quaternion().setFromEuler(entry.rest));
                const rest=new THREE.Quaternion().setFromEuler(entry.rest);
                const angle=rest.angleTo(target);
                if(angle>1.2)target.slerpQuaternions(rest,target,1.2/angle);
                entry.bone.quaternion.slerp(target,alpha);
            }
            for (const entry of this.fingers.filter(f=>f.side===side)) {
                if (!hand) {
                    entry.bone.quaternion.slerp(entry.rest,alpha);
                    continue;
                }
                const points=hand?.world || hand?.landmarks;
                const rawAngle=fingerJointCurl(points,entry.finger,entry.segment);
                const angle=clamp(rawAngle-.04,0,entry.finger===0?1.1:1.6);
                const target=entry.rest.clone();
                if(entry.spreadAxis && points?.length===21) {
                    const vector=(a,b)=>new THREE.Vector3(points[a].x-points[b].x,points[a].y-points[b].y,points[a].z-points[b].z);
                    const normal=vector(5,0).cross(vector(17,0)).normalize().multiplyScalar(left?-1:1);
                    const reference=vector(10,9).normalize(), base=entry.finger*4+1;
                    const direction=vector(base+1,base).normalize();
                    const spread=Math.atan2(normal.dot(reference.clone().cross(direction)),reference.dot(direction));
                    if(normal.lengthSq()>1e-8 && reference.lengthSq()>1e-8 && direction.lengthSq()>1e-8) {
                        target.multiply(new THREE.Quaternion().setFromAxisAngle(entry.spreadAxis,clamp(spread-entry.restSpread,-.45,.45)));
                    }
                }
                target.multiply(new THREE.Quaternion().setFromAxisAngle(entry.bendAxis,angle));
                entry.bone.quaternion.slerp(target,alpha);
            }
        }
    }
    solveArm(side,target,alpha,elbowTarget=null) {
        const bones=this.viewer.animationBones;
        const end=bones[side+'Wrist']?.bone;
        if(!end) return;
        // Bounded CCD follows the full arm chain, including the clavicle when
        // the rig has one. This spreads motion across the shoulder, upper arm,
        // and elbow instead of twisting the arm around a fixed shoulder.
        const chain = [side+'Elbow', side+'Arm', side+'Shoulder'].filter(key => bones[key]?.bone);
        if (!target?.toArray().every(Number.isFinite)) return;
        const handRange=clamp(this.viewer.trackingOptions?.handRange ?? 1.3,.5,2);
        const anchor=bones.head?.bone || bones[side+'Shoulder']?.bone || bones[side+'Arm']?.bone;
        if(anchor && handRange!==1) {
            const origin=anchor.getWorldPosition(new THREE.Vector3());
            target=origin.clone().add(target.clone().sub(origin).multiplyScalar(handRange));
            if(elbowTarget)elbowTarget=origin.clone().add(elbowTarget.clone().sub(origin).multiplyScalar(handRange));
        }
        this.handTargets ||= {};
        if (!this.handTargets[side]) this.handTargets[side]=target.clone();
        else this.handTargets[side].lerp(target,alpha);
        target=this.handTargets[side];
        const previous=new Map();
        for(const key of chain) {
            const entry=bones[key];
            previous.set(key,entry.bone.quaternion.clone());
            if(entry.rest)entry.bone.quaternion.setFromEuler(entry.rest);
        }
        this.root.updateMatrixWorld(true);
        const solve=(effector,joints,destination,passes)=>{
            if(!effector || !destination) return;
            for(let pass=0;pass<passes;pass++) for(const key of joints) {
                const joint=bones[key]?.bone; if(!joint?.parent) continue;
                this.root.updateMatrixWorld(true);
                const origin=joint.getWorldPosition(new THREE.Vector3());
                const from=effector.getWorldPosition(new THREE.Vector3()).sub(origin).normalize();
                const to=destination.clone().sub(origin).normalize();
                if(from.lengthSq()<1e-8 || to.lengthSq()<1e-8) continue;
                const correction=new THREE.Quaternion().setFromUnitVectors(from,to);
                const world=joint.getWorldQuaternion(new THREE.Quaternion());
                const parent=joint.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
                const local=parent.multiply(correction.multiply(world));
                joint.quaternion.slerp(local,.55);
                const entry=bones[key];
                if(entry.rest) {
                    const rest=new THREE.Quaternion().setFromEuler(entry.rest);
                    const limit=key.endsWith('Shoulder')?.5:key.endsWith('Elbow')?2.4:2.2;
                    const angle=rest.angleTo(joint.quaternion);
                    if(angle>limit)joint.quaternion.slerpQuaternions(rest,joint.quaternion,limit/angle);
                }
            }
        };
        if(elbowTarget && bones[side+'Elbow']?.bone) solve(bones[side+'Elbow'].bone,[side+'Arm',side+'Shoulder'],elbowTarget,3);
        solve(end,chain,target,4);
        for(const key of chain) {
            const bone=bones[key].bone, solved=bone.quaternion.clone();
            bone.quaternion.copy(previous.get(key)).slerp(solved,alpha);
        }
    }
}
