const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const pending = new Map();
let pixels;
let fetchImpl = async () => ({ ok: false });
const context = {
    console: { log() {}, warn() {}, error() {}, info() {} },
    performance,
    window: {},
    repairNoseSkin() { return 0; },
    fetch: (...args) => fetchImpl(...args),
    THREE: {
        Loader: class { constructor(manager) { this.manager = manager; } },
        LoadingManager: class { addHandler() {} setURLModifier() {} },
        FileLoader: class { setResponseType() {} load(url, done) { done(new ArrayBuffer(18)); } },
        Texture: class {},
    },
    TGALoader: class { parse() { return { width: 1, height: 1, data: new Uint8Array([255, 0, 0, 255]) }; } },
    DDSLoader: class {},
    ArmClearance: class { constructor(viewer) {this.root=viewer.model;} update() {} },
    ImageData: class { constructor(data, width, height) { Object.assign(this, { data, width, height }); } },
    document: { createElement() { return { getContext() { return { putImageData(image) { pixels = image; } }; } }; } },
    MMDLoader: class {
        constructor(manager) { this.manager = manager; }
        load(url, onLoad, onProgress, onError) {
            pending.set(url, { onLoad: model => { const result = onLoad(model); this.manager.onLoad(); return result; }, onError });
        }
    },
};
let source = fs.readFileSync('static/js/model-viewer.js', 'utf8')
    .replace(/^import .*;\r?\n/gm, '').replace('export default class ModelViewer', 'class ModelViewer');
vm.runInNewContext(source + '\nthis.ModelViewer = ModelViewer; this.SmartTgaLoader = SmartTgaLoader;', context);
const viewer = Object.create(context.ModelViewer.prototype);
const scene = new Set();
Object.assign(viewer, {
    loadGeneration: 0, model: null, placeholderGroup: null,
    physics: { detach() {}, attach() { return { bones: 0 }; } },
    scene: { add(model) { scene.add(model); } },
    renderer: { domElement: {style: {}}, renderLists: { dispose() {} }, compileAsync: async () => {} },
    _autoFrame(model) { this.framed = model; },
    setQuality() {},
    _indexMorphTargets(model) { this.allMorphNames = [model.name]; },
});
function mesh(name) {
    const resource = () => ({ disposed: 0, dispose() { this.disposed++; } });
    const texture = Object.assign(resource(), { isTexture: true });
    const material = Object.assign(resource(), { map: texture, uniforms: { map: { value: texture } } });
    const geometry = Object.assign(resource(), {userData:{MMD:{bones:['センター','上半身','頭','左腕','右腕','左足','右足'].map(boneName=>({name:boneName}))}}}), skeleton = resource();
    return { name, isSkinnedMesh:true, geometry, skeleton, material, texture,
        removeFromParent() { scene.delete(this); }, traverse(fn) { fn(this); } };
}
const tick = () => new Promise(resolve => setImmediate(resolve));
(async () => {
    let loadedTexture;
    const texture = new context.SmartTgaLoader({ resolveURL: url => url })
        .load('skin.tga', result => { loadedTexture = result; });
    assert.equal(loadedTexture, texture);
    assert.equal(texture.image.width, 1);
    assert.equal(texture.image.height, 1);
    assert.deepEqual(Array.from(pixels.data), [255, 0, 0, 255]);
    assert.equal(texture.needsUpdate, true, 'TGA pixels ready for rendering');
    let first = mesh('Evelyn');
    const initial = viewer.loadModel('evelyn');
    await tick(); pending.get('evelyn').onLoad(first); await initial;
    const kafkaPromise = viewer.loadModel('kafka');
    assert.equal(scene.size, 0, 'Previous model removed immediately');
    for (const resource of [first.geometry, first.skeleton, first.material, first.texture]) {
        assert.equal(resource.disposed, 1, 'GPU resources released once');
    }
    await tick();
    const evelynPromise = viewer.loadModel('evelyn2'); await tick();
    const second = mesh('Evelyn2'); pending.get('evelyn2').onLoad(second); await evelynPromise;
    const stale = mesh('Kafka'); pending.get('kafka').onLoad(stale);
    assert.equal(await kafkaPromise, null);
    assert.equal(stale.geometry.disposed, 1);
    assert.deepEqual([...scene], [second], 'Late Kafka must not overlap Evelyn');
    assert.equal(viewer.framed, second, 'Stale loads must not move the camera');
    const oldError = viewer.loadModel('old-error'); await tick();
    const newest = viewer.loadModel('newest'); await tick();
    pending.get('old-error').onError(new Error('late failure'));
    assert.equal(await oldError, null, 'Stale failures ignored');
    const newestMesh = mesh('newest'); pending.get('newest').onLoad(newestMesh); await newest;
    const failure = viewer.loadModel('failure'); await tick();
    pending.get('failure').onError(new Error('bad PMX'));
    await assert.rejects(failure, /bad PMX/);
    assert.equal(scene.size, 0, 'Failed switch leaves no previous model');
    let release;
    fetchImpl = () => new Promise(resolve => { release = resolve; });
    const metadata = viewer.loadModel('metadata');
    fetchImpl = async () => ({ ok: false });
    const winner = viewer.loadModel('winner'); await tick();
    release({ ok: false }); assert.equal(await metadata, null);
    assert.equal(pending.has('metadata'), false, 'Superseded metadata must not start loading');
    pending.get('winner').onLoad(mesh('winner')); await winner;
    assert.equal(scene.size, 1);
    let finishCompile;
    viewer.renderer.compileAsync = () => new Promise(resolve => { finishCompile = resolve; });
    const compiling = viewer.loadModel('compiling'); await tick();
    const compilingMesh = mesh('compiling'); pending.get('compiling').onLoad(compilingMesh); await tick();
    assert.equal(scene.size, 0, 'Model waits for GPU shaders before display');
    const savedFinish = finishCompile;
    viewer.renderer.compileAsync = async () => {};
    const replacement = viewer.loadModel('replacement'); await tick();
    const replacementMesh = mesh('replacement'); pending.get('replacement').onLoad(replacementMesh);
    await replacement; savedFinish();
    assert.equal(await compiling, null, 'Switch during GPU preparation cancels the old model');
    assert.equal(compilingMesh.geometry.disposed, 1);
    assert.deepEqual([...scene], [replacementMesh]);
    viewer.renderer.compileAsync = async () => { throw new Error('GPU compilation failed'); };
    const gpuFailure = viewer.loadModel('gpu-failure'); await tick();
    const brokenMesh = mesh('gpu-failure'); pending.get('gpu-failure').onLoad(brokenMesh);
    await assert.rejects(gpuFailure, /GPU compilation failed/);
    assert.equal(brokenMesh.geometry.disposed, 1);
    assert.equal(scene.size, 0);
    viewer.renderer.compileAsync = async () => {};
    const sanitize = viewer._sanitizeGeometry;
    viewer._sanitizeGeometry = () => { throw new Error('Geometry preparation failed'); };
    const preparationFailure = viewer.loadModel('preparation-failure'); await tick();
    const badGeometry = mesh('preparation-failure'); pending.get('preparation-failure').onLoad(badGeometry);
    await assert.rejects(preparationFailure, /Geometry preparation failed/);
    assert.equal(badGeometry.geometry.disposed, 1);
    assert.equal(scene.size, 0);
    viewer._sanitizeGeometry = sanitize;
    const attach = viewer.physics.attach;
    viewer.physics.attach = () => { throw new Error('Physics setup failed'); };
    const setupFailure = viewer.loadModel('setup-failure'); await tick();
    const badRig = mesh('setup-failure'); pending.get('setup-failure').onLoad(badRig);
    await assert.rejects(setupFailure, /Physics setup failed/);
    assert.equal(viewer.model, null);
    assert.equal(badRig.geometry.disposed, 1);
    assert.equal(scene.size, 0);
    viewer.physics.attach = attach;
    // Bone motion is relative to the original pose, so it cannot accumulate.
    const rotation = { x: 0.1, y: 0.2, z: 0.3, order: 'XYZ',
        clone() { return { x: this.x, y: this.y, z: this.z, order: this.order }; },
        set(x, y, z) { Object.assign(this, { x, y, z }); } };
    const head = { isBone: true, name: '頭', rotation };
    viewer.morphMap = {};
    viewer._setupCharacterAnimation({ traverse(fn) { fn(head); } });
    Object.assign(viewer, { model: {}, talkBlend: 1, thinkBlend: 0,
        speechLevel: 0.8, activity: 'talking', emotion: 'friendly' });
    viewer._animateCharacter(1 / 60, 1);
    const pose = { x: rotation.x, y: rotation.y, z: rotation.z };
    for (let i = 0; i < 100; i++) viewer._animateCharacter(1 / 60, 1);
    // Gestures now have their own clock. Repeating the idle clock must not
    // accumulate rotations, even while a conversation gesture advances.
    for (let i = 0; i < 600; i++) viewer._animateCharacter(1 / 60, 1);
    assert.ok(Math.abs(rotation.x - pose.x) < .04 && Math.abs(rotation.y - pose.y) < .08
        && Math.abs(rotation.z - pose.z) < .02, 'Pose never accumulates drift');
    assert.ok(Math.abs(rotation.x - 0.1) < 0.04, 'Talking nod is bounded');
    viewer.setActivity('idle');
    for (let i = 0; i < 120; i++) viewer._animateCharacter(1 / 60, 1);
    assert.ok(viewer.talkBlend < 0.001, 'Talking gesture fades back to idle');
    viewer.setActivity('thinking');
    for (let i = 0; i < 120; i++) viewer._animateCharacter(1 / 60, 1);
    assert.ok(viewer.thinkBlend > 0.99);
    viewer.setEmotionFromText('I am sorry you are feeling sad.');
    assert.equal(viewer.emotion, 'concerned');
    const leftArm = { isBone: true, name: '左腕', rotation: { ...rotation } };
    const rightArm = { isBone: true, name: '右腕', rotation: { ...rotation } };
    viewer._setupCharacterAnimation({ traverse(fn) { fn(leftArm); fn(rightArm); } });
    const leftRest = leftArm.rotation.z, rightRest = rightArm.rotation.z;
    viewer.setActivity('idle');
    viewer.talkBlend = 0; viewer.thinkBlend = 0;
    viewer._animateCharacter(1 / 60, 0);
    assert.ok(leftArm.rotation.z < leftRest - 0.6, 'Idle lowers the left arm out of A-pose');
    assert.ok(rightArm.rotation.z > rightRest + 0.6, 'Idle lowers the right arm out of A-pose');
    viewer.setActivity('talking'); viewer.talkBlend = 1; viewer.speechLevel = 0.8;
    for (let i = 0; i < 80; i++) viewer._animateCharacter(1 / 60, 1);
    const leftLift = leftArm.rotation.z - leftRest + 0.72;
    const rightLift = rightRest + 0.72 - rightArm.rotation.z;
    assert.ok(Math.abs(leftLift - rightLift) > 0.01, 'Talking hands use asymmetric gestures');
    console.log('PASS: immediate removal, resource disposal, out-of-order loads, stale failures, current failures, metadata races, TGA pixel decoding, GPU preparation races and errors, bounded animation and activity transitions');
})().catch(err => { console.error(err); process.exitCode = 1; });
