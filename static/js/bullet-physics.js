import * as THREE from 'three';
import { MMDPhysics } from 'three/addons/animation/MMDPhysics.js';

let ready, activeOwner;
const constructors = new Map();
export function initializeBullet() {
    if (ready) return ready;
    ready = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = '/static/vendor/ammo/ammo.wasm.js';
        script.onerror = () => reject(new Error('Bullet runtime could not load'));
        script.onload = async () => {
            try {
                const binding = await globalThis.Ammo({locateFile: file => '/static/vendor/ammo/' + file});
                // The upstream MMD adapter pools temporary native objects but
                // has no world disposal API. Track owned constructor results
                // (never borrowed getters) so switching models frees Bullet.
                globalThis.Ammo = new Proxy(binding, {get(target, key) {
                    const value = target[key];
                    if (typeof value !== 'function' || !String(key).startsWith('bt')) return value;
                    if (!constructors.has(key)) constructors.set(key, new Proxy(value, {construct(Type, args) {
                        const object = Reflect.construct(Type, args);
                        if (activeOwner) activeOwner.allocations.push({type:key, object});
                        return object;
                    }}));
                    return constructors.get(key);
                }});
                resolve(globalThis.Ammo);
            } catch (error) { reject(error); }
        };
        document.head.appendChild(script);
    });
    ready.catch(() => { ready = null; });
    return ready;
}

const finite3 = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite);
export function validBulletRig(mesh) {
    const rig = mesh?.geometry?.userData?.MMD;
    const bodies = rig?.rigidBodies, joints = rig?.constraints;
    if (!Array.isArray(bodies) || !bodies.some(body => body.type === 1 || body.type === 2) || !Array.isArray(joints)) return false;
    const count = mesh.skeleton?.bones?.length || 0;
    return bodies.every(body => Number.isInteger(body.boneIndex) && body.boneIndex >= -1 && body.boneIndex < count
        && [0,1,2].includes(body.type) && [0,1,2].includes(body.shapeType)
        && finite3(body.position) && finite3(body.rotation)
        && ['width','height','depth','weight','positionDamping','rotationDamping','friction','restitution'].every(key => Number.isFinite(body[key]) && body[key] >= 0)
        && (body.width > 0 || (body.type === 0 && body.width === 0))
        && (body.shapeType !== 1 || (body.height > 0 && body.depth > 0)))
        && joints.every(joint => [joint.rigidBodyIndex1,joint.rigidBodyIndex2].every(i => Number.isInteger(i) && i >= 0 && i < bodies.length)
            && ['position','rotation','translationLimitation1','translationLimitation2','rotationLimitation1','rotationLimitation2','springPosition','springRotation'].every(key => finite3(joint[key])));
}

export default class BulletPhysics {
    constructor(mesh, skipBones = null) {
        this.allocations = [];
        this.mesh = mesh;
        this.rest = mesh.skeleton.bones.map(bone => ({bone, position:bone.position.clone(), quaternion:bone.quaternion.clone()}));
        const rig = mesh.geometry.userData.MMD;
        // Some ports intentionally export zero-radius static bone anchors.
        // Stabilize just those colliders with a tiny radius; preserve dynamics,
        // body indices and every joint, and never modify the source metadata.
        // Glitch-fix excluded bones keep their collider as a kinematic body
        // (converted type 0) so nearby cloth still collides, but Bullet no
        // longer simulates or drives their bones.
        const bodies = rig.rigidBodies.map(body => {
            let adjusted = body.type === 0 && body.width === 0
                ? {...body, width: .001} : body;
            if (skipBones?.has(adjusted.boneIndex) && adjusted.type !== 0) adjusted = {...adjusted, type: 0};
            return adjusted;
        });
        const parent = mesh.parent, position = mesh.position.clone(), quaternion = mesh.quaternion.clone(), scale = mesh.scale.clone();
        try {
            this.owned(() => {
                this.engine = new MMDPhysics(mesh, bodies, rig.constraints, {unitStep:1/65,maxStepNum:4});
                this.gravity = new Ammo.btVector3(0,-98,0);
                this.zero = new Ammo.btVector3(0,0,0);
                this.windForce = new Ammo.btVector3(0,0,0);
                this.dragImpulse = new Ammo.btVector3(0,0,0);
            });
        } catch (error) { this.dispose(); throw error; }
        finally { mesh.parent = parent; mesh.position.copy(position); mesh.quaternion.copy(quaternion); mesh.scale.copy(scale); mesh.updateMatrixWorld(true); }
        for (const rigid of this.engine.bodies) {
            const worldRotation = new THREE.Quaternion(), parentRotation = new THREE.Quaternion();
            // The upstream adapter assumes an animation mixer restores the
            // physics bones each frame. Multiplying its world correction by
            // last frame's local rotation accumulates twists in persistent
            // webcam poses. Convert the Bullet world pose directly to local.
            rigid._updateBoneRotation = function () {
                const transform = this._getWorldTransformForBone();
                const basis = this.manager.getBasis(transform);
                try {
                    worldRotation.set(basis.x(), basis.y(), basis.z(), basis.w()).normalize();
                    if (this.bone.parent) this.bone.parent.getWorldQuaternion(parentRotation);
                    else parentRotation.identity();
                    this.bone.quaternion.copy(parentRotation.invert().multiply(worldRotation)).normalize();
                } finally {
                    this.manager.freeQuaternion(basis);
                    this.manager.freeTransform(transform);
                }
            };
        }
        const dynamicBones = new Set(this.engine.bodies.filter(rigid => rigid.params.type !== 0).map(rigid=>rigid.bone));
        this.idleAnchors = this.engine.bodies.filter(rigid => {
            if(rigid.params.type !== 0) return false;
            // Static stabilizers nested inside dynamic hair/cloth follow the
            // solver itself; they are not user/animation wake-up sources.
            for(let bone=rigid.bone;bone?.isBone;bone=bone.parent)if(dynamicBones.has(bone))return false;
            return true;
        })
            .map(rigid => ({bone:rigid.bone, matrix:new Float64Array(rigid.bone.matrixWorld.elements)}));
    }
    owned(fn) {
        const previous = activeOwner; activeOwner = this;
        try { return fn(); } finally { activeOwner = previous; }
    }
    setMode(mode) {
        this.setStrength({off:0,subtle:.55,normal:1,lively:1.35}[mode] ?? 1);
        this.mode = mode;
    }
    setStrength(value) {
        if (!Number.isFinite(value)) return;
        const factor = Math.max(0,Math.min(1.5,value));
        const wasOff = this.mode === 'off';
        this.hairDrag?.set(0,0,0);
        this.strength = factor;
        this.idleTime = 0;
        this.mode = factor === 0 ? 'off' : 'custom';
        this.accumulator = 0;
        if (factor === 0 || wasOff) {
            this.restore();
            this.owned(() => this.engine.reset());
        }
        // Strength changes responsiveness, not the character's weight. Reducing
        // gravity made tightly constrained hair/cloth drift away from its pose.
        this.gravity.setValue(0,factor === 0 ? 0 : -98,0); this.engine.world.setGravity(this.gravity);
        for (const rigid of this.engine.bodies) {
            const damping = factor < 1 ? .15*(1-factor)/.45 : -.04*(factor-1)/.35;
            rigid.body.setDamping(Math.min(1,Math.max(0,rigid.params.positionDamping+damping)),Math.min(1,Math.max(0,rigid.params.rotationDamping+damping)));
            if (factor === 0 || wasOff) {rigid.body.setLinearVelocity(this.zero); rigid.body.setAngularVelocity(this.zero);}
            if(rigid.params.type !== 0) {
                const threshold = factor === 1 && !(this.windStrength > 0) ? .08 : 0;
                rigid.body.setSleepingThresholds(threshold,threshold);
                rigid.body.activate(true);
            }
        }
        for (const joint of this.engine.constraints) {
            const stiffness = factor < 1 ? 1+.35*(1-factor)/.45 : 1-.25*(factor-1)/.35;
            for (let i=0;i<3;i++) {
                joint.constraint.setStiffness(i,joint.params.springPosition[i]*stiffness);
                joint.constraint.setStiffness(i+3,joint.params.springRotation[i]*stiffness);
            }
        }
    }
    restore() {
        for (const {bone,position,quaternion} of this.rest) { bone.position.copy(position); bone.quaternion.copy(quaternion); bone.updateMatrix(); }
        this.mesh.updateMatrixWorld(true);
    }
    setWindStrength(value) {
        this.windStrength = Math.max(0,Math.min(1,value));
        this.idleTime = 0;
        for(const rigid of this.engine.bodies) {
            if(rigid.params.type === 0) continue;
            const threshold = this.strength === 1 && this.windStrength === 0 ? .08 : 0;
            rigid.body.setSleepingThresholds(threshold,threshold);
            rigid.body.activate(true);
        }
    }
    update(delta) {
        if (this.mode === 'off') return;
        if (!Number.isFinite(delta) || delta <= 0) return;
        if(this.allowIdleSleep && this.strength === 1 && !this.windStrength && this.idleAnchors.length) {
            this.mesh.updateWorldMatrix(true,true);
            let moved=false;
            for(const anchor of this.idleAnchors) {
                const current=anchor.bone.matrixWorld.elements;
                for(let i=0;i<16;i++)if(Math.abs(current[i]-anchor.matrix[i])>1e-4){moved=true;break;}
            }
            if(moved) {
                this.idleTime=0;
                for(const anchor of this.idleAnchors)anchor.matrix.set(anchor.bone.matrixWorld.elements);
            } else this.idleTime=(this.idleTime||0)+Math.min(delta,.1);
            // Kinematic anchors keep connected Bullet islands awake even with
            // sleeping thresholds. Hold the settled pose while genuinely idle;
            // accumulated anchor movement, gestures or wind immediately wake it.
            if(this.idleTime>=3){this.accumulator=0;return;}
        } else this.idleTime=0;
        // MMDPhysics rounds short updates up to its unit step. Accumulate
        // here so 120 Hz screens do not simulate twice as fast as 60 Hz.
        const step = 1/65;
        this.accumulator = (this.accumulator || 0) + Math.min(delta,4*step);
        let count = 0;
        while (this.accumulator >= step) {
            // Webcam retargeting writes local head/arm rotations after the
            // previous render. Kinematic colliders must use THIS frame's pose.
            this.mesh.updateMatrixWorld(true);
            if (this.hairDrag?.lengthSq() > 0) {
                for (const rigid of this.engine.bodies) {
                    if (rigid.params.type === 0 || rigid.params.weight <= 0 || !this.hairBones.has(rigid.bone)) continue;
                    const gain = -2 * rigid.params.weight;
                    this.dragImpulse.setValue(this.hairDrag.x*gain,this.hairDrag.y*gain,this.hairDrag.z*gain);
                    rigid.body.activate(true);
                    rigid.body.applyCentralImpulse(this.dragImpulse);
                }
                this.hairDrag.set(0,0,0);
            }
            if (this.windStrength > 0) {
                this.windTime = (this.windTime || 0) + step;
                for (const rigid of this.engine.bodies) {
                    if (rigid.params.type === 0 || rigid.params.weight <= 0) continue;
                    // A breeze must keep changing, rather than settle into an
                    // almost invisible constant lean. Acceleration is capped
                    // below normal gravity at full strength and normal physics;
                    // authored constraints/colliders still limit cloth motion.
                    const force = this.windStrength * this.strength * rigid.params.weight * 65;
                    const gust = .55 + .45*Math.sin(this.windTime*1.1);
                    this.windForce.setValue(force*gust,0,force*.65*Math.sin(this.windTime*.73));
                    rigid.body.activate(true);
                    rigid.body.applyCentralForce(this.windForce);
                }
            }
            this.owned(() => this.engine.update(step));
            this.accumulator -= step;
            if (++count >= 4) { this.accumulator = 0; break; }
        }
    }
    applyBoneImpulse(displacement, bones) {
        if (this.mode === 'off' || !bones.size || !this.engine) return;
        const length = Math.sqrt(displacement.lengthSq());
        const scale = length > 1 ? 1 / length : 1;
        for (const rigid of this.engine.bodies) {
            if (rigid.params.type === 0 || rigid.params.weight <= 0 || !bones.has(rigid.bone)) continue;
            const gain = -2 * rigid.params.weight * scale;
            this.dragImpulse.setValue(displacement.x*gain, displacement.y*gain, displacement.z*gain);
            rigid.body.activate(true);
            rigid.body.applyCentralImpulse(this.dragImpulse);
        }
        this.idleTime = 0;
    }
    applyHairDrag(displacement) {
        if (this.mode === 'off' || !this.hairBones?.size) return;
        // Queue input until a simulation step; never allocate native objects
        // per mouse event or feed drag forces into skirt/body/accessory rigs.
        this.hairDrag ??= new THREE.Vector3();
        this.hairDrag.add(displacement).clampLength(0, 1);
        this.idleTime = 0;
    }
    dispose(restoreBones = true) {
        const world = this.engine?.world || this.allocations.find(a => a.type === 'btDiscreteDynamicsWorld')?.object;
        if (world) {
            for (const {type,object} of this.allocations) {
                if (type === 'btGeneric6DofSpringConstraint') world.removeConstraint(object);
                if (type === 'btRigidBody') world.removeRigidBody(object);
            }
        }
        for (const {object} of this.allocations.reverse()) Ammo.destroy(object);
        this.allocations = [];
        this.engine = null;
        if (restoreBones) this.restore();
    }
}
