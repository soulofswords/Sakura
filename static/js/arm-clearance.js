import * as THREE from 'three';

/** Lightweight clothing/body clearance for procedural AI gestures.
 * Sample visible torso/skirt geometry once, then use a small radial envelope.
 * Only rotate arm joints; never move vertices, scale limbs or alter source rigs.
 */
export default class ArmClearance {
    constructor(viewer) {
        this.root = viewer.model;
        this.bones = viewer.animationBones;
        this.point = new THREE.Vector3(); this.end = new THREE.Vector3();
        this.elbow = new THREE.Vector3(); this.target = new THREE.Vector3();
        this.mid = new THREE.Vector3(); this.identity = new THREE.Quaternion();
        this.origin = new THREE.Vector3(); this.from = new THREE.Vector3(); this.to = new THREE.Vector3();
        this.correction = new THREE.Quaternion(); this.world = new THREE.Quaternion(); this.parent = new THREE.Quaternion();
        this.inverse = new THREE.Matrix4(); this.center = new THREE.Vector3();
        this.metrics = { corrections: 0, before: 0, after: 0 };
        this.arms = [];
        this.root.updateMatrixWorld(true);
        this.inverse.copy(this.root.matrixWorld).invert();
        const torso = this.bones.chest?.bone || this.bones.torso?.bone;
        const head = this.bones.head?.bone;
        if (!torso || !head) return;
        torso.getWorldPosition(this.center).applyMatrix4(this.inverse);
        const headY = head.getWorldPosition(this.point).applyMatrix4(this.inverse).y;
        const excluded = new Set();
        let span = 0;
        for (const side of ['left', 'right']) {
            const upper = this.bones[side + 'Arm']?.bone, lower = this.bones[side + 'Elbow']?.bone, hand = this.bones[side + 'Wrist']?.bone;
            if (!upper || !lower || !hand) continue;
            upper.traverse(b => excluded.add(b));
            viewer.vrm?.humanoid?.getRawBoneNode(side + 'UpperArm')?.traverse(b => excluded.add(b));
            upper.getWorldPosition(this.origin).applyMatrix4(this.inverse);
            lower.getWorldPosition(this.elbow).applyMatrix4(this.inverse);
            hand.getWorldPosition(this.end).applyMatrix4(this.inverse);
            const reach = this.origin.distanceTo(this.elbow) + this.elbow.distanceTo(this.end);
            if (!Number.isFinite(reach) || reach <= 1e-5) continue;
            const sign = Math.sign(this.origin.x - this.center.x) || (side === 'left' ? 1 : -1);
            span = Math.max(span, Math.abs(this.origin.x - this.center.x));
            this.arms.push({side,upper,lower,hand,sign,reach,padding:reach*.055});
        }
        if (this.arms.length === 0 || span < 1e-5 || headY <= this.center.y) return;
        this.span = span;
        const height = Math.max(headY - this.center.y, span);
        this.bottom = this.center.y - height * 1.6;
        this.top = this.center.y + height * .35;
        this.bands = Array.from({length:12}, () => ({x:span*.62,z:span*.45}));
        let budget = 6000;
        this.root.traverse(mesh => {
            if (!mesh.isSkinnedMesh || !mesh.visible || budget <= 0) return;
            const g = mesh.geometry, skin = g.attributes.skinIndex, weights = g.attributes.skinWeight;
            if (!g.attributes.position || !skin || !weights) return;
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            const groups = g.groups.length ? g.groups : [{start:0,count:g.index?.count || g.attributes.position.count,materialIndex:0}];
            for (const group of groups) {
                const m = materials[group.materialIndex];
                if (!m || !m.visible || m.opacity < .1 || /髪|发|髮|hair|翼|羽|wing|尾|tail/i.test(m.name || '')) continue;
                const step = Math.max(3, Math.ceil(group.count / 800 / 3) * 3);
                for (let i=group.start; i<group.start+group.count && budget>0; i+=step) {
                    budget--;
                    const index = g.index ? g.index.getX(i) : i;
                    let armWeight = 0;
                    for (let c=0;c<4;c++) if (excluded.has(mesh.skeleton.bones[skin.getComponent(index,c)])) armWeight += weights.getComponent(index,c);
                    if (armWeight > .35) continue;
                    mesh.getVertexPosition(index,this.point).applyMatrix4(mesh.matrixWorld).applyMatrix4(this.inverse);
                    if (![this.point.x,this.point.y,this.point.z].every(Number.isFinite)) continue;
                    if (this.point.y < this.bottom || this.point.y > this.top) continue;
                    const x = Math.abs(this.point.x-this.center.x), z = Math.abs(this.point.z-this.center.z);
                    if (x>span*2.4 || z>span*2) continue; // ignore helper geometry and distant accessories
                    const bin = Math.min(11,Math.floor((this.point.y-this.bottom)/(this.top-this.bottom)*12));
                    this.bands[bin].x=Math.max(this.bands[bin].x,x);
                    this.bands[bin].z=Math.max(this.bands[bin].z,z);
                }
            }
        });
        // Fill gaps in sampling without shrinking neighboring clothing surfaces.
        const rest = this.bands.map(b => ({...b}));
        this.bands.forEach((b,i)=>{for(const n of [i-1,i+1]) if(rest[n]) {
            b.x=Math.max(b.x,rest[n].x*.9); b.z=Math.max(b.z,rest[n].z*.9);
        }});
    }

    project(point, arm) {
        if (!this.bands || point.y < this.bottom || point.y > this.top) return 0;
        const coordinate = Math.max(0,Math.min(11,(point.y-this.bottom)/(this.top-this.bottom)*12-.5));
        const low = Math.floor(coordinate), high = Math.min(11,low+1), t=coordinate-low;
        const rx = THREE.MathUtils.lerp(this.bands[low].x,this.bands[high].x,t)+arm.padding;
        const rz = THREE.MathUtils.lerp(this.bands[low].z,this.bands[high].z,t)+arm.padding;
        const x=point.x-this.center.x,z=point.z-this.center.z;
        const distance=Math.hypot(x/rx,z/rz);
        if (distance >= 1) return 0;
        // Keep hands on their own side, rather than pushing them through the torso.
        point.x=this.center.x+arm.sign*(rx*Math.sqrt(Math.max(0,1-(z/rz)**2))+arm.padding*.15);
        return 1-distance;
    }

    penetration(arm) {
        arm.hand.getWorldPosition(this.end).applyMatrix4(this.inverse);
        arm.lower.getWorldPosition(this.elbow).applyMatrix4(this.inverse);
        let depth=0;
        for (const t of [1,.65]) {
            this.point.copy(this.elbow).lerp(this.end,t);
            depth=Math.max(depth,this.project(this.point,arm));
        }
        return depth;
    }

    update() {
        if (!this.bands) return;
        this.root.updateMatrixWorld(true);
        this.inverse.copy(this.root.matrixWorld).invert();
        this.metrics.before=0;this.metrics.after=0;
        for (const arm of this.arms) {
            const before=this.penetration(arm); this.metrics.before=Math.max(this.metrics.before,before);
            if (before <= 0) continue;
            for(let pass=0;pass<4;pass++) {
                arm.hand.getWorldPosition(this.end).applyMatrix4(this.inverse);
                this.target.copy(this.end);
                let depth=this.project(this.target,arm);
                arm.lower.getWorldPosition(this.elbow).applyMatrix4(this.inverse);
                this.point.copy(this.elbow).lerp(this.end,.65);
                this.mid.copy(this.point);
                const midDepth=this.project(this.point,arm);
                if (midDepth>depth) {this.target.copy(this.end).addScaledVector(this.point.sub(this.mid),1/.65);depth=midDepth;}
                if(depth<=0) break;
                this.target.applyMatrix4(this.root.matrixWorld);
                for(const joint of [arm.lower,arm.upper]) {
                    joint.getWorldPosition(this.origin);arm.hand.getWorldPosition(this.end);
                    this.from.subVectors(this.end,this.origin);this.to.subVectors(this.target,this.origin);
                    if(this.from.lengthSq()<1e-8 || this.to.lengthSq()<1e-8) continue;
                    this.correction.setFromUnitVectors(this.from.normalize(),this.to.normalize());
                    const angle=2*Math.acos(Math.min(1,Math.abs(this.correction.w)));
                    if(angle>.12) this.correction.slerp(this.identity,1-.12/angle);
                    joint.getWorldQuaternion(this.world);joint.parent.getWorldQuaternion(this.parent).invert();
                    joint.quaternion.copy(this.parent.multiply(this.correction.multiply(this.world))).normalize();
                    joint.updateMatrix();joint.updateMatrixWorld(true);
                }
            }
            this.metrics.after=Math.max(this.metrics.after,this.penetration(arm));
            this.metrics.corrections++;
        }
    }
}
