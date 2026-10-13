import * as THREE from 'three';
import BulletPhysics, { initializeBullet, validBulletRig } from './bullet-physics.js?v=drag-speech23';

/**
 * Game-style character physics for the Sakura model viewer.
 *
 * MMD (PMX/PMD) models ship their own physics rig: rigid bodies bound to
 * bones (hair strands, skirts, chests, ribbons, tails). MMDLoader exposes
 * that rig in geometry.userData.MMD without simulating it, so characters
 * moved like statues. Valid rigs now run through Bullet rigid bodies and
 * constraints. Missing/broken rigs fall back to a verlet spring-chain solver.
 *
 * Bone selection order:
 *   1. PMX rigid bodies whose body type is dynamic (1 or 2). Static bodies
 *      (type 0) are kinematic colliders and are not simulated.
 *   2. Name heuristics, for models exported without usable rigid bodies.
 *   3. VRM avatars: the vendored three-vrm simulates spring bones inside
 *      vrm.update(); this module only reports their presence.
 */

const MODES = {
    subtle: { gravity: 0.55, stiffness: 1.35, drag: 0.04, wind: 0.35 },
    normal: { gravity: 1.0, stiffness: 1.0, drag: 0.0, wind: 1.0 },
    lively: { gravity: 1.5, stiffness: 0.72, drag: -0.05, wind: 1.8 },
};

// Per-category feel. drag is the fraction of velocity lost per 1/60s step;
// stiffness is the per-step pull toward the kinematic target at 60fps.
const BASE_PARAMS = {
    hair: { stiffness: 0.22, gravity: 30, drag: 0.20, maxAngle: 50 },
    breast: { stiffness: 0.22, gravity: 20, drag: 0.24, maxAngle: 18 },
    skirt: { stiffness: 0.32, gravity: 34, drag: 0.25, maxAngle: 38 },
    other: { stiffness: 0.25, gravity: 26, drag: 0.20, maxAngle: 48 },
};

// Fallback detection for models whose rigid bodies are missing or all
// static. Substring matching on purpose: bone names glue words together
// with underscores (_yure_hair_soft), so word boundaries never fire. The
// categories only tune spring feel, and patterns are checked in order
// (breast → hair → skirt → other), so overlap is harmless.
const FALLBACK_PATTERNS = [
    ['breast', /(?:胸|乳|おっぱい|bust|breast|boob|oppai)/i],
    // Game ports (Genshin, Honkai...) name hair bones with 发/髮 and skirts
    // with 裙, alongside the Japanese originals.
    ['hair', /髪|发|髮|辫|辮|ツインテール|ツインテ|おさげ|ポニーテール|アホ毛|三つ編み|hair|ponytail|twintail|pigtails|ahoge|braid/i],
    ['skirt', /スカート|裾|フリル|マフラー|裙|skirt|frill|muffler|scarf/i],
    ['other', /リボン|尻尾|しっぽ|羽|袖|ネクタイ|ベルト|ポンポン|飘带|飄帶|丝带|絲帶|缎带|緞帶|尾|披风|披風|配饰|配飾|饰品|飾品|挂件|掛件|ribbon|tail|wing|sleeve|tie|belt|pompom|accessory|cape|coat/i],
];

// Scratch objects — the solver runs every frame, so nothing allocates here.
const _p = new THREE.Vector3();
const _target = new THREE.Vector3();
const _restDir = new THREE.Vector3();
const _vel = new THREE.Vector3();
const _acc = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _qParent = new THREE.Quaternion();
const _qRest = new THREE.Quaternion();
const _qWorld = new THREE.Quaternion();
const _qFix = new THREE.Quaternion();
const _qIdentity = new THREE.Quaternion();
const _matWorld = new THREE.Matrix4();
const _restMatrix = new THREE.Matrix4();
const _rotationMatrix = new THREE.Matrix4();
const _collisionMid = new THREE.Vector3();
const _collisionAxis = new THREE.Vector3();
const _collisionTangent = new THREE.Vector3();
const _collisionDelta = new THREE.Vector3();
const HAIR_COLLISION_SAMPLES = [.18, .45, .72, 1];

function classifyBone(name) {
    const n = String(name || '');
    for (const [category, pattern] of FALLBACK_PATTERNS) {
        if (pattern.test(n)) return category;
    }
    return null;
}

function classifyRigBone(bone, name) {
    const category = classifyBone(name) || 'other';
    // Some ports reuse skirt-chain names for hair. The actual attachment
    // hierarchy identifies these without rewriting the model's bones/rig.
    if (category === 'skirt' || category === 'other') {
        for (let parent = bone.parent; parent?.isBone; parent = parent.parent) {
            if (/^(?:頭|头|頭部|头部|head(?:[_ .-]?\d+)?)$/i.test(parent.name)) return 'hair';
        }
    }
    return category;
}

function usableBone(bone) {
    return bone?.isBone && [...bone.position.toArray(), ...bone.quaternion.toArray(), ...bone.scale.toArray()].every(Number.isFinite)
        && bone.quaternion.lengthSq() > 1e-8 && bone.scale.toArray().every(v => Math.abs(v) > 1e-8);
}

export default class ModelPhysics {
    constructor() {
        this.mode = 'normal';
        this.strength = 1;
        this.windStrength = 0;
        this.model = null;
        this.source = null;
        this.nodes = [];
        this.info = null;
        this.time = 0;
        this._accumulator = 0;
        this._chain = []; // ancestor matrices, reused every step
        this.bullet = null;
        this.bulletReady = false;
        // PMX physics rigs vary widely in quality. Use the deterministic
        // spring-chain solver by default so an imported rig cannot explode
        // on its first Bullet step. Bullet remains an explicit opt-in.
        this.forceSpring = true;
        this.forceSpringReason = 'Safe spring-chain physics is active for PMX rigs to prevent unstable rigid-body motion.';
        this._bulletJitterWindow = [];
        this.glitchFixEnabled = false;
        // New rigs are checked on every attach. An explicit per-model choice
        // may opt in or out; otherwise only structurally identical pivots are
        // excluded automatically.
        this.glitchFixPolicy = 'auto';
        this._rigContext = null;
    }

    /**
     * Only flag structurally duplicated pivots: same name, same direct
     * parent and effectively identical local position. Repeated names alone
     * are common and valid in PMX skirt panels, so never remove those chains.
     * Candidates are excluded from simulation without modifying the model.
     */
    detectGlitchBones() {
        const context = this._rigContext;
        const result = { indices: new Set(), groups: [], zeroLength: [], detected: 0 };
        if (!context) return result;
        const { mmdBones } = context;
        const bones = context.mesh.skeleton.bones;
        for (let i = 0; i < mmdBones.length; i++) {
            const entry = mmdBones[i];
            if (!entry || (entry.rigidBodyType !== 1 && entry.rigidBodyType !== 2)) continue;
            const name = String(entry.name || '');
            if (!name) continue;
            const bone = bones[i];
            if (!bone) continue;
            let group = result.groups.find(candidate => candidate.name === name
                && candidate.parent === entry.parent
                && bones[candidate.kept]?.position.distanceToSquared(bone.position) <= 1e-8);
            if (!group) result.groups.push({ name, parent: entry.parent, kept: i, removed: [] });
            else { result.indices.add(i); group.removed.push(i); }
        }
        result.detected = result.indices.size;
        return result;
    }

    async initialize(model) {
        this.requireBullet = true;
        this.bulletReady = false;
        if (this.forceSpring) return;
        let mesh = null;
        model.traverse(child => { if (!mesh && child.isSkinnedMesh && validBulletRig(child)) mesh = child; });
        if (!mesh) return;
        try { await initializeBullet(); this.bulletReady = true; }
        catch (error) { this.bulletReady = false; console.warn('Bullet unavailable; spring fallback:', error); }
    }

    setMode(mode) {
        if (!(mode in MODES) && mode !== 'off') return false;
        const wasOff = this.mode === 'off';
        this.mode = mode;
        this.strength = {off:0,subtle:.55,normal:1,lively:1.5}[mode];
        if (this.bullet) { this.bullet.setMode(mode); this._resetBulletJitterGuard(); return true; }
        if (mode === 'off') {
            this._restoreRest();
        } else if (wasOff || !this.info) {
            this.reset();
        }
        return true;
    }

    setStrength(value) {
        if (!Number.isFinite(value)) return false;
        const wasOff = this.mode === 'off';
        this.strength = Math.max(0,Math.min(1.5,value));
        this.mode = this.strength === 0 ? 'off' : 'custom';
        if (this.bullet) { this.bullet.setStrength(this.strength); this._resetBulletJitterGuard(); }
        else if (this.mode === 'off') this._restoreRest();
        else if (wasOff) this.reset();
        return true;
    }

    setWindStrength(value) {
        if (!Number.isFinite(value)) return false;
        this.windStrength = Math.max(0,Math.min(1,value));
        if (this.bullet) { this.bullet.setWindStrength(this.windStrength); this._resetBulletJitterGuard(); }
        return true;
    }

    _resetBulletJitterGuard() {
        this._bulletJitterWindow = [];
        for (const node of this.nodes) {
            node._previousBulletRotation ||= new THREE.Quaternion();
            node._previousBulletRotation.copy(node.bone.quaternion);
        }
    }

    _bulletJitterDetected() {
        let hairJumps = 0, skirtJumps = 0;
        const jumpLimit = 0.70 + this.windStrength * 0.45;
        for (const node of this.nodes) {
            if (node.category !== 'hair' && node.category !== 'skirt') continue;
            node._previousBulletRotation ||= node.bone.quaternion.clone();
            const jump = node._previousBulletRotation.angleTo(node.bone.quaternion);
            node._previousBulletRotation.copy(node.bone.quaternion);
            // A single hard swing can be normal. Several hair/skirt bones
            // rotating over 40 degrees in one rendered frame points to an
            // unstable authored constraint set on an imported model.
            if (jump > jumpLimit) {
                if (node.category === 'hair') hairJumps++;
                else skirtJumps++;
            }
        }
        this._bulletJitterWindow.push(hairJumps >= 3 || skirtJumps >= 3);
        if (this._bulletJitterWindow.length > 5) this._bulletJitterWindow.shift();
        return this._bulletJitterWindow.filter(Boolean).length >= 2;
    }

    _switchToSafeSprings(reason) {
        // Keep the pose that exposed the bad constraints. Restoring every
        // skeleton bone to bind pose here would visibly pop the avatar.
        this.bullet?.dispose(false);
        this.bullet = null;
        if (!this.info) return;
        // Adopt the current physics pose as the spring solver's rest pose so
        // the handoff stays continuous. Keep original rest values for Off.
        for (const node of this.nodes) {
            node.springRestLocal = node.bone.position.clone();
            node.springRestQuat = node.bone.quaternion.clone();
        }
        this.info.engine = 'spring fallback';
        this.info.rigidBodies = 0;
        this.info.joints = 0;
        this.info.warning = reason;
        this._bulletUnstableFrames = 0;
        this._accumulator = 0;
        this._bulletJitterWindow = [];
        this._seedSpringsFromCurrentPose();
        console.warn(reason);
        if (globalThis.CustomEvent) globalThis.window?.dispatchEvent(new CustomEvent('sakura-physics-status-changed'));
    }

    _seedSpringsFromCurrentPose() {
        if (!this.model) return;
        this.model.updateMatrixWorld(true);
        for (const node of this.nodes) {
            _target.copy(node.tailLocal).applyMatrix4(node.bone.matrixWorld);
            node.pos ||= new THREE.Vector3();
            node.prev ||= new THREE.Vector3();
            node.pos.copy(_target);
            node.prev.copy(_target);
        }
    }

    /** Attach a PMX/PMD SkinnedMesh loaded by MMDLoader. */
    attach(model, reservedNames = null) {
        this.detach();
        this.model = model;
        this.time = 0;

        let mesh = null;
        model.traverse(child => {
            if (mesh || !child.isSkinnedMesh) return;
            const mmdBones = child.geometry?.userData?.MMD?.bones;
            if (Array.isArray(mmdBones) && mmdBones.length && mmdBones.length === child.skeleton?.bones?.length) mesh = child;
        });

        let indices = new Set();
        let skeletonBones = [];
        let categoryOf = () => 'other';
        let depthOf = () => 0;
        let parentOf = () => -1;
        const excludedBones = new Set();

        if (mesh) {
            const mmdBones = mesh.geometry.userData.MMD.bones;
            const bones = mesh.skeleton.bones;
            this._rigContext = { mesh, mmdBones };
            const candidates = this.detectGlitchBones().indices;
            this.glitchFixEnabled = this.glitchFixPolicy === 'on'
                || (this.glitchFixPolicy === 'auto' && candidates.size > 0);
            const skipBones = this.glitchFixEnabled ? candidates : new Set();
            for (const index of skipBones) if (bones[index]) excludedBones.add(bones[index]);
            const boneIndex = new Map(bones.map((bone, index) => [bone, index]));
            const validRig = mmdBones.every((entry, index) => entry && usableBone(bones[index])
                && Number.isInteger(entry.parent) && entry.parent >= -1 && entry.parent < bones.length
                && entry.parent !== index
                && entry.parent === (boneIndex.get(bones[index].parent) ?? -1));
            // Dynamic rigid bodies (type 1/2) mark the bones MMD itself
            // simulates. Static ones (type 0) only collide.
            const byRig = new Set();
            for (let i = 0; i < mmdBones.length; i++) {
                if (mmdBones[i]?.rigidBodyType === 1 || mmdBones[i]?.rigidBodyType === 2) byRig.add(i);
            }
            if (validRig && byRig.size > 0) {
                // The glitch-bone exclusion applies before both the spring
                // solver and Bullet see the bone set.
                for (const index of skipBones) byRig.delete(index);
                if (byRig.size > 0 && (this.forceSpring || !this.requireBullet || validBulletRig(mesh))) {
                    // Even one dynamic body is the author's physics intent; the
                    // name fallback below is only for models with none at all.
                    indices = byRig;
                    skeletonBones = mesh.skeleton.bones;
                    categoryOf = index => classifyRigBone(bones[index], mmdBones[index].name);
                    depthOf = ModelPhysics._buildDepthTable(mmdBones);
                    parentOf = index => mmdBones[index].parent;
                    this.source = 'model rig';
                    this._skipBones = skipBones;
                } else {
                    // A structurally valid PMX can still need name-based
                    // springs. Keep its exclusion set and rig diagnostics.
                    mesh = null;
                    this._skipBones = skipBones;
                }
            } else {
                // Keep the PMX context when a malformed Bullet rig falls back
                // to name matching, so automatic exclusions and diagnostics
                // remain available for that fallback too.
                if (byRig.size === 0) {
                    this._rigContext = null;
                    this._skipBones = null;
                } else {
                    this._skipBones = skipBones;
                }
                mesh = null;
            }
        }

        if (!mesh) {
            // Name-based fallback over the skeleton, excluding bones the
            // viewer animates itself (spine, head, arms...).
            const reserved = reservedNames || new Set();
            const boneIndex = new Map();
            const allBones = [];
            model.traverse(child => { if (child.isBone) { boneIndex.set(child, allBones.length); allBones.push(child); } });
            for (const bone of allBones) {
                if (usableBone(bone) && classifyBone(bone.name) && !reserved.has(bone.name) && !excludedBones.has(bone)) indices.add(boneIndex.get(bone));
            }
            if (!indices.size) {
                this.source = 'none';
                this.info = { source: 'none', chains: 0, bones: 0, categories: {} };
                this._setGlitchInfo();
                return this.info;
            }
            skeletonBones = allBones;
            const table = allBones.map((bone, index) => ({
                index,
                parent: bone.parent?.isBone ? boneIndex.get(bone.parent) : -1,
                name: bone.name,
            }));
            categoryOf = index => classifyBone(allBones[index].name) || 'other';
            depthOf = ModelPhysics._buildDepthTable(table);
            parentOf = index => table[index].parent;
            this.source = 'name match';
        }

        const bones = skeletonBones;
        // Some PMX exports mark only hair/skirt as dynamic even though they
        // have weighted chest secondary bones. Include explicit secondary
        // names, never the humanoid torso or gesture-controlled bones.
        for (let i = 0; i < bones.length; i++) {
            if (classifyBone(bones[i].name) === 'breast'
                && !/^(?:chest|spine\d*|胸|上半身\d*)$/i.test(bones[i].name)
                && !reservedNames?.has(bones[i].name) && !excludedBones.has(bones[i])
                && usableBone(bones[i])) indices.add(i);
        }
        this.hairColliders = [];
        if (mesh) for (const body of mesh.geometry.userData.MMD.rigidBodies || []) {
            if (body.type !== 0 || ![0,1,2].includes(body.shapeType)
                || ![...body.position, ...body.rotation, body.width, body.height, body.depth].every(Number.isFinite)) continue;
            const bone = bones[body.boneIndex] || mesh;
            const offset = new THREE.Matrix4().compose(new THREE.Vector3().fromArray(body.position),
                new THREE.Quaternion().setFromEuler(new THREE.Euler(...body.rotation)), new THREE.Vector3(1,1,1));
            this.hairColliders.push({bone, offset, world:new THREE.Matrix4(), inverse:new THREE.Matrix4(), center:new THREE.Vector3(), maxScale:1, boundRadius:0, shape:body.shapeType,
                radius:Math.max(.01,body.width), height:Math.max(0,body.height),
                size:new THREE.Vector3(Math.max(.01,body.width),Math.max(.01,body.height),Math.max(.01,body.depth))});
        }
        const chainRoots = new Set();
        for (const index of indices) {
            if (!indices.has(parentOf(index))) chainRoots.add(index);
        }
        // Branching hair strands and skirt columns share physics roots; each
        // root gets its own wind phase so strands do not sway in lockstep.
        const rootPhase = new Map();
        let rootCounter = 0;
        for (const root of chainRoots) rootPhase.set(root, (rootCounter++) * 1.37);

        let nodes = [];
        for (const index of indices) {
            const bone = bones[index];
            const restLocal = bone.position.clone();
            const category = categoryOf(index);
            const child = bone.children.find(child => child.isBone && child.position.lengthSq() > 1e-8);
            // Simulate this bone's tail, anchored at its own origin. Rotating
            // the bone can move a tail, but cannot move its own origin.
            const tailLocal = child && child.position.toArray().every(Number.isFinite) ? child.position.clone() : category === 'breast' ? new THREE.Vector3(0, 0, .35) : restLocal.clone();
            // A root/leaf at zero offset still needs a virtual tail to rotate.
            if (tailLocal.lengthSq() < 1e-8) tailLocal.set(0, 0.2, 0);
            let chainDepth = 0;
            for (let walk = parentOf(index); indices.has(walk); walk = parentOf(walk)) chainDepth++;
            // Scalp attachments stay firm, but a long strand should bend
            // progressively rather than pulling every middle segment back
            // with the same root stiffness. Cap the taper for very long rigs.
            const hairFlex = category === 'hair' ? 1 / (1 + Math.min(chainDepth, 6) * .30) : 1;
            nodes.push({
                index,
                bone,
                restLocal,
                tailLocal,
                restQuat: bone.quaternion.clone(),
                restLen: tailLocal.length(),
                depth: depthOf(index),
                chainDepth,
                phase: rootPhase.get(this._chainRootOf(index, indices, parentOf)) || 0,
                category,
                params: category === 'hair'
                    ? {...BASE_PARAMS.hair, stiffness: BASE_PARAMS.hair.stiffness * hairFlex}
                    : BASE_PARAMS[category] || BASE_PARAMS.other,
            });
        }
        nodes.sort((a, b) => a.depth - b.depth);
        this.nodes = nodes;

        const categories = {};
        for (const node of nodes) categories[node.category] = (categories[node.category] || 0) + 1;

        this.info = {
            source: this.source,
            chains: chainRoots.size,
            bones: this.nodes.length,
            categories,
        };
        this.reset();
        this.info.engine = this.forceSpring ? 'spring-chain' : 'spring fallback';
        this.info.rigidBodies = 0;
        this.info.joints = 0;
        if (this.forceSpring) this.info.warning = this.forceSpringReason || 'Using stable spring-chain physics for this model.';
        if (!this.forceSpring && this.bulletReady && mesh && validBulletRig(mesh)) {
            try {
                this.bullet = new BulletPhysics(mesh, this._skipBones);
                this.bullet.hairBones = new Set(this.nodes.filter(node => node.category === 'hair').map(node => node.bone));
                if (this.mode === 'custom') this.bullet.setStrength(this.strength);
                else this.bullet.setMode(this.mode);
                this.bullet.setWindStrength(this.windStrength);
                this.info.engine = 'Bullet';
                this.info.rigidBodies = this.bullet.engine.bodies.length;
                this.info.joints = this.bullet.engine.constraints.length;
                this._resetBulletJitterGuard();
            } catch (error) {
                this.bullet?.dispose(); this.bullet = null;
                console.warn('Broken Bullet rig; using springs:', error);
            }
        }
        this._setGlitchInfo();
        return this.info;
    }

    _setGlitchInfo() {
        if (!this._rigContext || !this.info) return;
        const detection = this.detectGlitchBones();
        this.info.glitch = {
            detected: detection.detected,
            active: Boolean(this.glitchFixEnabled && this._skipBones?.size),
            removed: this.glitchFixEnabled ? (this._skipBones?.size || 0) : 0,
            groups: detection.groups.filter(group => group.removed.length)
                .map(group => ({ name: group.name, removed: group.removed.length })),
            zeroLength: detection.zeroLength.length,
        };
    }

    /** Attach a VRM avatar; three-vrm drives its spring bones in vrm.update(). */
    attachVrm(vrm) {
        this.detach();
        this.model = vrm.scene;
        // The manager exposes joints as a Set (size), older builds as an array.
        const jointList = vrm.springBoneManager?.joints;
        const joints = jointList ? (jointList.size ?? jointList.length ?? 0) : 0;
        this.vrmPhysicsJoints = jointList ? [...jointList] : [];
        this.vrmHairJoints = jointList ? [...jointList].filter(joint =>
            joint.bone && classifyBone(joint.bone.name) === 'hair') : [];
        this.source = joints ? 'vrm springbone' : 'none';
        this.info = { source: this.source, chains: 0, bones: joints,
            categories: {hair: this.vrmHairJoints.length} };
        return this.info;
    }

    detach() {
        this.bullet?.dispose();
        this.bullet = null;
        this._restoreRest();
        this.model = null;
        this.nodes = [];
        this.vrmHairJoints = [];
        this.vrmPhysicsJoints = [];
        this.hairColliders = [];
        this._speechEnvelope = 0;
        this.info = null;
        this.source = null;
        this._accumulator = 0;
        this._bulletUnstableFrames = 0;
        this._bulletJitterWindow = [];
        this._rigContext = null;
        this._skipBones = null;
    }

    /** Snap every particle onto its kinematic target (attach, mode changes). */
    reset() {
        if (!this.model || !this.nodes.length) return;
        this.model.updateMatrixWorld(true);
        for (const node of this.nodes) {
            const parentWorld = this._parentWorld(node.bone.parent);
            if(node.diagnosticStatic){
                node.bone.position.copy(node.restLocal);node.bone.quaternion.copy(node.restQuat);node.bone.updateMatrix();
                _target.copy(node.tailLocal).applyMatrix4(node.bone.matrix).applyMatrix4(parentWorld);
                node.pos.copy(_target);node.prev.copy(_target);continue;
            }
            _restMatrix.compose(node.springRestLocal || node.restLocal, node.springRestQuat || node.restQuat, node.bone.scale).premultiply(parentWorld);
            _target.copy(node.tailLocal).applyMatrix4(_restMatrix);
            node.pos = node.pos || new THREE.Vector3();
            node.prev = node.prev || new THREE.Vector3();
            node.pos.copy(_target);
            node.prev.copy(_target);
        }
    }

    update(delta) {
        if (this.bullet) {
            this.bullet.allowIdleSleep = Boolean(this.allowIdleSleep);
            this.bullet.update(delta);
            if (this._bulletJitterDetected()) {
                this._switchToSafeSprings('Unstable hair/skirt bone motion detected; safer spring-chain physics is active.');
                return;
            }
            // Some imported rigs pass structural validation but their joints
            // still fold/stretch multiple hair segments through a full turn.
            // Require sustained corruption, not one energetic tracked frame,
            // before switching to the already-detected spring chains.
            let brokenHair = 0;
            for (const node of this.nodes) {
                if (node.category !== 'hair') continue;
                const bone = node.bone;
                if (!Number.isFinite(bone.position.x + bone.position.y + bone.position.z + bone.quaternion.w)
                    || bone.position.distanceTo(node.restLocal) > Math.max(.2, node.restLocal.length() * 1.5)
                    || bone.quaternion.angleTo(node.restQuat) > 2.8) brokenHair++;
            }
            this._bulletUnstableFrames = Math.max(0, (this._bulletUnstableFrames || 0) + (brokenHair >= 2 ? 1 : -.15));
            if (this._bulletUnstableFrames >= 12) {
                this._switchToSafeSprings('Unstable hair/skirt rig detected; safer spring-chain physics is active.');
            }
            return;
        }
        if (!this.nodes.length || !this.model) return;
        // VRM spring bones advance inside vrm.update(delta).
        if (this.source === 'vrm springbone') return;
        const f = this.strength;
        const preset = this.mode === 'custom' ? {
            gravity:1, stiffness:f<1?1+.35*(1-f):1-.56*(f-1),
            drag:f<1?.08*(1-f):-.1*(f-1), wind:f,
        } : MODES[this.mode];
        if (!preset) return;

        // Fixed 60 Hz substeps: verlet velocity carries the previous step's
        // duration, so a variable step would change spring strength and
        // gravity sag between 30 and 60 fps displays.
        this.model.updateMatrixWorld(true);
        this._accumulator = Math.min((this._accumulator || 0) + Math.min(delta, 0.1), 0.2);
        const step = 1 / 60;
        let substeps = 0;
        while (this._accumulator >= step) {
            this._step(preset, step);
            this._accumulator -= step;
            if (++substeps >= 4) { this._accumulator = 0; break; } // drop backlog after a stall
        }
    }

    /** Screen/window dragging is virtual root motion, applied only to hair. */
    applyHairDrag(displacement) {
        if (!this.model || this.mode === 'off' || !displacement?.isVector3
            || !Number.isFinite(displacement.x + displacement.y + displacement.z)) return;
        if (this.bullet) { this.bullet.applyHairDrag(displacement); return; }
        if (this.source === 'vrm springbone') {
            // The vendored VRM runtime stores its Verlet tails in each joint's
            // center space. Inject velocity there, retaining authored spring
            // settings and collisions. Only explicitly named hair is eligible.
            for (const joint of this.vrmHairJoints || []) {
                if (!joint._prevTail?.isVector3) continue;
                _vel.copy(displacement).clampLength(0, 1).multiplyScalar(2 / 60);
                if (joint.center) {
                    if (Math.abs(joint.center.matrixWorld.determinant()) < 1e-12) continue;
                    _matWorld.copy(joint.center.matrixWorld).invert();
                    _vel.applyMatrix4(_matWorld).sub(_p.setFromMatrixPosition(_matWorld));
                }
                joint._prevTail.add(_vel);
            }
            return;
        }
        // Inject bounded Verlet velocity, without moving any cloth particles.
        _vel.copy(displacement).clampLength(0, 1).multiplyScalar(2 / 60);
        for (const node of this.nodes) {
            if (node.category === 'hair' && node.prev) node.prev.add(_vel);
        }
    }

    /** Bounded movement inertia for every authored/fallback dynamic chain. */
    applyCharacterDrag(displacement) {
        this._applyImpulse(displacement, false);
    }

    _applyImpulse(displacement, chestOnly) {
        if (!this.model || this.mode === 'off' || !displacement?.isVector3
            || !Number.isFinite(displacement.x + displacement.y + displacement.z)) return;
        const eligible = node => !chestOnly || (node.category === 'breast'
            && !/^(?:chest|spine\d*|胸|上半身\d*)$/i.test(node.bone.name));
        if (this.bullet) {
            const bones = new Set(this.nodes.filter(eligible).map(node => node.bone));
            this.bullet.applyBoneImpulse(displacement, bones);
            return;
        }
        _vel.copy(displacement).clampLength(0, 1).multiplyScalar(2 / 60);
        if (this.source === 'vrm springbone') {
            for (const joint of this.vrmPhysicsJoints || []) {
                if (!joint._prevTail?.isVector3 || !joint.bone
                    || !eligible({category:classifyBone(joint.bone.name),bone:joint.bone})) continue;
                _acc.copy(_vel);
                if (joint.center) {
                    if (Math.abs(joint.center.matrixWorld.determinant()) < 1e-12) continue;
                    _matWorld.copy(joint.center.matrixWorld).invert();
                    _acc.applyMatrix4(_matWorld).sub(_p.setFromMatrixPosition(_matWorld));
                }
                joint._prevTail.add(_acc);
            }
            return;
        }
        for (const node of this.nodes) {
            if (node.prev && eligible(node)) node.prev.addScaledVector(_vel, !chestOnly && node.category === 'breast' ? 2.5 : 1);
        }
    }

    /** Audio-envelope changes supply a small impulse, not an idle oscillator. */
    updateSpeechPhysics(level, delta) {
        level = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
        if (this.mode === 'off' || !this.model) { this._speechEnvelope = 0; return; }
        const previous = this._speechEnvelope || 0;
        this._speechEnvelope = previous + (level - previous)
            * (1 - Math.exp(-Math.max(0, Math.min(delta, .1)) / .12));
        const change = this._speechEnvelope - previous;
        if (Math.abs(change) < .0001) return;
        _dir.set(0, change * .45, change * .12);
        // Spring particles are world-space; Bullet owns unscaled mesh space.
        if (!this.bullet) _dir.applyQuaternion(this.model.getWorldQuaternion(_qWorld));
        this._applyImpulse(_dir, true);
    }

    /**
     * World matrix of a bone as an exact product of ancestor locals, instead
     * of the stale .matrixWorld three.js recomputes only at render time.
     * Solver-written bones refresh their .matrix on write, so chains resolve
     * through non-simulated helper bones and earlier nodes in the same step.
     */
    _parentWorld(bone) {
        let count = 0;
        for (let ancestor = bone; ancestor; ancestor = ancestor.parent) {
            this._chain[count++] = ancestor.matrix;
        }
        _matWorld.identity();
        for (let i = count - 1; i >= 0; i--) _matWorld.multiply(this._chain[i]);
        return _matWorld;
    }

    _step(preset, step) {
        this.time += step;
        const dt2 = step * step;
        // Indoor companion: movement supplies inertia, not perpetual wind.
        // Keep optional wind available for future environment effects, off by default.
        const windStrength = 12 * Math.max(0, Math.min(1, this.windStrength || 0)) * preset.wind;

        for (const collider of this.hairColliders || []) {
            collider.world.copy(this._parentWorld(collider.bone)).multiply(collider.offset);
            collider.inverse.copy(collider.world).invert();
            collider.center.setFromMatrixPosition(collider.world);
            const e = collider.world.elements;
            collider.maxScale = Math.max(Math.hypot(e[0],e[1],e[2]),Math.hypot(e[4],e[5],e[6]),Math.hypot(e[8],e[9],e[10]));
            const localRadius = collider.shape === 1
                ? Math.hypot(collider.size.x,collider.size.y,collider.size.z)
                : collider.shape === 2 ? Math.hypot(collider.radius,collider.height*.5+collider.radius) : collider.radius;
            collider.boundRadius = localRadius * collider.maxScale;
        }
        for (const node of this.nodes) {
            const parentWorld = this._parentWorld(node.bone.parent);
            const restLocal = node.springRestLocal || node.restLocal;
            const restQuat = node.springRestQuat || node.restQuat;
            if(node.diagnosticStatic){
                node.bone.position.copy(node.restLocal);node.bone.quaternion.copy(node.restQuat);node.bone.updateMatrix();
                _target.copy(node.tailLocal).applyMatrix4(node.bone.matrix).applyMatrix4(parentWorld);
                node.pos.copy(_target);node.prev.copy(_target);continue;
            }
            _p.copy(restLocal).applyMatrix4(parentWorld);
            _qParent.setFromRotationMatrix(_rotationMatrix.extractRotation(parentWorld));
            // Where the bone sits if it never left the rig this frame. Any
            // ancestor motion — breathing, gestures, root movement — flows
            // through here, and the verlet particle lagging behind it is the
            // inertia.
            _restMatrix.compose(restLocal, restQuat, node.bone.scale).premultiply(parentWorld);
            _target.copy(node.tailLocal).applyMatrix4(_restMatrix);
            const worldLength = _restDir.subVectors(_target, _p).length();
            if (worldLength < 1e-6) continue;
            _restDir.normalize();

            const stiffness = Math.min(0.92, Math.max(0.04, node.params.stiffness * preset.stiffness));
            const drag = Math.min(0.9, Math.max(-0.2, node.params.drag + preset.drag));
            const retention = Math.pow(1 - drag, step * 60);
            const pull = 1 - Math.pow(1 - stiffness, step * 60);
            _vel.subVectors(node.pos, node.prev).multiplyScalar(retention);
            node.prev.copy(node.pos);
            const depthFactor = 1 + Math.min(node.chainDepth, 4) * 0.15;
            _acc.set(
                Math.sin(this.time * 1.1 + node.phase) * windStrength * depthFactor,
                -node.params.gravity * preset.gravity,
                Math.cos(this.time * 0.9 + node.phase * 1.7) * windStrength * depthFactor
            ).multiplyScalar(dt2);
            node.pos.add(_vel).add(_acc);
            node.pos.lerp(_target, pull);

            // Bones cannot stretch: keep the rest distance from the parent.
            _dir.subVectors(node.pos, _p);
            const distance = _dir.length();
            if (distance < 1e-6) {
                node.pos.copy(_target);
            } else {
                node.pos.copy(_p).addScaledVector(_dir, worldLength / distance);
                _dir.normalize();
                // Cone limit keeps chains from folding through the body.
                const angle = _dir.angleTo(_restDir);
                const maxAngle = node.params.maxAngle * THREE.MathUtils.DEG2RAD;
                if (angle > maxAngle) {
                    _qFix.setFromUnitVectors(_dir, _restDir);
                    _qFix.slerpQuaternions(_qIdentity, _qFix, (angle - maxAngle) / Math.max(angle, 1e-5));
                    _dir.applyQuaternion(_qFix);
                    node.pos.copy(_p).addScaledVector(_dir, worldLength);
                }
            }

            if (node.category === 'hair') {
                this._collideHair(node, _p, _target, worldLength);
            }

            // A broken rig, teleport or huge spike must not fling hair into
            // orbit: any particle far from its target snaps back to rest.
            if (!Number.isFinite(node.pos.x + node.pos.y + node.pos.z)
                || node.pos.distanceTo(_target) > worldLength * 4 + 3) {
                node.pos.copy(_target);
                node.prev.copy(_target);
            }

            // Rotate this bone around its own origin to match the tail,
            // then refresh its local matrix so descendant
            // chains build on it this step.
            _dir.subVectors(node.pos, _p).normalize();
            _qFix.setFromUnitVectors(_restDir, _dir);
            _qRest.copy(_qParent).multiply(restQuat);
            _qWorld.copy(_qRest).premultiply(_qFix);
            node.bone.quaternion.copy(_qParent).invert().multiply(_qWorld);
            node.bone.updateMatrix();
        }
    }

    _collideHair(node, anchor, restTail, length) {
        // Check points along the strand as well as its tip. Project against
        // authored head/body/clothing volumes in their moving local space.
        const point = this._collisionPoint ||= new THREE.Vector3();
        const closest = this._collisionClosest ||= new THREE.Vector3();
        const correction = this._collisionCorrection ||= new THREE.Vector3();
        const forward = this._collisionForward ||= new THREE.Matrix4();
        const nearby = this._nearbyHairColliders ||= [];
        // Four samples with four correction passes cover the visible strand
        // while keeping the per-frame cost bounded on rigs with many bodies.
        _collisionMid.addVectors(anchor,node.pos).multiplyScalar(.5);
        nearby.length = 0;
        for (const c of this.hairColliders || []) {
            if (!c.center) { nearby.push(c); continue; }
            const reach = length*.5 + (c.boundRadius || 0) + .12;
            if (_collisionMid.distanceToSquared(c.center) <= reach*reach) nearby.push(c);
        }
        if (!nearby.length) return;
        for (let pass=0; pass<4; pass++) {
          let changed = false;
          for (const c of nearby) {
            forward.copy(c.world || c.inverse.clone().invert());
            for (const fraction of HAIR_COLLISION_SAMPLES) {
                point.lerpVectors(anchor,node.pos,fraction).applyMatrix4(c.inverse);
                const padding = Math.min(.12,Math.max(.025,length*.06));
                let penetrates = false;
                if(c.shape===1) {
                    const gx=c.size.x+padding-Math.abs(point.x), gy=c.size.y+padding-Math.abs(point.y), gz=c.size.z+padding-Math.abs(point.z);
                    if(gx>0 && gy>0 && gz>0) {
                        correction.copy(point);
                        if(gx<=gy && gx<=gz) correction.x=(point.x<0?-1:1)*(c.size.x+padding);
                        else if(gy<=gz) correction.y=(point.y<0?-1:1)*(c.size.y+padding);
                        else correction.z=(point.z<0?-1:1)*(c.size.z+padding);
                        penetrates = true;
                    }
                } else {
                    closest.set(0,c.shape===2?THREE.MathUtils.clamp(point.y,-c.height/2,c.height/2):0,0);
                    correction.subVectors(point,closest);
                    const d=correction.length(),r=c.radius+padding;
                    if(d<r) {
                        if(d<1e-6) correction.set(0,0,1); else correction.divideScalar(d);
                        correction.multiplyScalar(r).add(closest);penetrates = true;
                    }
                }
                if (!penetrates) continue;
                // A root may start inside the head collider in a valid PMX
                // rig. Keep only that short scalp attachment untouched;
                // middle and lower strand points must still be kept outside
                // skin/clothing even when the authored rest pose intersects.
                if (fraction <= .18) {
                    const restPoint = this._collisionRest ||= new THREE.Vector3();
                    restPoint.lerpVectors(anchor,restTail,fraction).applyMatrix4(c.inverse);
                    let rootPenetrates;
                    if (c.shape === 1) rootPenetrates = Math.abs(restPoint.x)<c.size.x+padding
                        && Math.abs(restPoint.y)<c.size.y+padding && Math.abs(restPoint.z)<c.size.z+padding;
                    else {
                        const rootCenter = c.shape===2 ? THREE.MathUtils.clamp(restPoint.y,-c.height/2,c.height/2) : 0;
                        rootPenetrates = Math.hypot(restPoint.x,restPoint.y-rootCenter,restPoint.z) < c.radius+padding;
                    }
                    if (rootPenetrates) continue;
                }
                correction.applyMatrix4(forward);point.applyMatrix4(forward);
                _collisionDelta.subVectors(correction,point);
                // With a fixed-length strand, pushing along its own axis is
                // erased by the length constraint. Turn near-radial pushes
                // into a tangent swing so a strand can move around a shoulder
                // collider instead of snapping back through it.
                _collisionAxis.subVectors(node.pos,anchor).normalize();
                if (_collisionDelta.lengthSq() > 1e-10
                    && Math.abs(_collisionDelta.dot(_collisionAxis) / _collisionDelta.length()) > .88) {
                    _collisionTangent.subVectors(c.center || anchor,anchor);
                    _collisionTangent.cross(_collisionAxis);
                    if (_collisionTangent.lengthSq() < 1e-8) {
                        _collisionTangent.set(1,0,0);
                        if (Math.abs(_collisionAxis.x) > .8) _collisionTangent.set(0,0,1);
                        _collisionTangent.crossVectors(_collisionAxis,_collisionTangent);
                    }
                    _collisionDelta.copy(_collisionTangent).setLength(Math.max(.02,_collisionDelta.length()));
                }
                node.pos.addScaledVector(_collisionDelta,1/fraction);
                node.pos.sub(anchor).clampLength(length,length).add(anchor);
                node.prev.lerp(node.pos,.25); // damp collision chatter
                _collisionMid.addVectors(anchor,node.pos).multiplyScalar(.5);
                changed = true;
            }
          }
          if (!changed) break;
        }
    }

    _chainRootOf(index, indices, parentOf) {
        let current = index;
        while (indices.has(parentOf(current))) current = parentOf(current);
        return current;
    }

    _restoreRest() {
        for (const node of this.nodes) {
            node.bone.position.copy(node.restLocal);
            node.bone.quaternion.copy(node.restQuat);
            node.bone.updateMatrix();
            node.springRestLocal = null;
            node.springRestQuat = null;
        }
    }

    /** Depth of every bone from the model root, via PMX parent indices. */
    static _buildDepthTable(table) {
        const depths = new Array(table.length).fill(undefined);
        const depth = index => {
            let d = depths[index];
            if (d !== undefined) return d;
            const parent = table[index].parent;
            d = parent >= 0 && parent < table.length && parent !== index ? depth(parent) + 1 : 0;
            depths[index] = d;
            return d;
        };
        for (let i = 0; i < table.length; i++) depth(i);
        return index => (index >= 0 && index < depths.length ? depths[index] : 0);
    }
}
