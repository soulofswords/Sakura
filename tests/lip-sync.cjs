const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let fetchImpl = async () => ({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) });
let decodeImpl = async () => ({});
let amplitude = 0.012;
const frames = new Map(); let frameId = 0;
const sources = [];
class AudioContext {
    state = 'suspended'; sampleRate = 48000; currentTime = 0; destination = {};
    async resume() { this.state = 'running'; }
    decodeAudioData(buffer) { return decodeImpl(buffer); }
    createBufferSource() {
        const source = { started: false, stopped: false, connect() {}, disconnect() {},
            start() { this.started = true; }, stop() { this.stopped = true; } };
        sources.push(source); return source;
    }
    createAnalyser() { return { fftSize: 0, frequencyBinCount: 512, connect() {}, disconnect() {},
        getByteFrequencyData(data) { data.fill(100); },
        getFloatTimeDomainData(data) { data.fill(amplitude); } }; }
    createGain() { return {gain:{value:1},connect(){},disconnect(){}}; }
}
const context = { console, AbortController, window: { AudioContext },
    document: { getElementById() { return null; } },
    fetch: (...args) => fetchImpl(...args),
    requestAnimationFrame(fn) { frames.set(++frameId, fn); return frameId; },
    cancelAnimationFrame(id) { frames.delete(id); } };
vm.runInNewContext(fs.readFileSync('static/js/lip-sync.js', 'utf8')
    .replace('export default class LipSync', 'class LipSync') + '\nthis.LipSync = LipSync;', context);
const viewer = { resolvedVowels: { A: 'a', I: 'i', U: 'u', E: 'e', O: 'o' }, resetMouth() { this.weights = {}; },
    setVowelWeights(weights) { this.weights = { ...weights }; } };
const sync = new context.LipSync(viewer);
const tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; };
function frame(delta) {
    const [id, fn] = frames.entries().next().value;
    frames.delete(id); sync.audioContext.currentTime += delta; fn();
}
(async () => {
    // Quiet converted audio and louder speech should animate consistently.
    const clip = level => ({ sampleRate: 16000, getChannelData: () =>
        Float32Array.from({ length: 1600 }, (_, i) => i < 800 ? level : 0) });
    sync._prepareEnvelope(clip(0.02));
    const quietOpening = sync._openingAt(0.02);
    assert.equal(sync._openingAt(-0.01), 0, 'No mouth movement before audible playback');
    assert.equal(sync._openingAt(0.08), 0, 'Silent parts of a clip close the mouth');
    assert.equal(sync._openingAt(1), 0, 'No mouth movement after a clip');
    sync._prepareEnvelope(clip(0.2));
    assert.ok(Math.abs(sync._openingAt(0.02) - quietOpening) < 0.001,
        'Clip volume should not change lip sync strength');
    sync.envelope = null;
    const silent = new Float32Array(1600);
    const voice = Float32Array.from({ length: 1600 }, () => 0.1);
    sync._prepareEnvelope({ sampleRate: 16000, numberOfChannels: 2,
        getChannelData: channel => channel ? voice : silent });
    assert.ok(sync._openingAt(0.02) > 0, 'Speech in the right stereo channel must animate PMX mouths');
    sync.envelope = null;
    // Equivalent elapsed time gives the same motion across frame rates.
    for (const rising of [true, false]) {
        const values = [30, 60, 144].map(fps => {
            sync.current = { A: rising ? 0 : 1, I: 0, U: 0, E: 0, O: 0 };
            sync.targets = { A: rising ? 1 : 0, I: 0, U: 0, E: 0, O: 0 };
            for (let n = 0; n < fps; n++) sync._smoothWeights(1 / fps);
            return sync.current.A;
        });
        assert.ok(Math.max(...values) - Math.min(...values) < 1e-12);
    }
    let started = 0;
    const playing = sync.playWithLipSync('quiet', () => { assert.ok(sync.source.started); started++; });
    assert.equal(started, 0, 'Reply stays pending until decoded playback starts');
    await tick();
    assert.equal(started, 1, 'Reply is revealed exactly once at playback start');
    assert.equal(sync.audioContext.state, 'running');
    assert.equal(viewer.audioPlaybackActive, true, 'Decoded playback takes audio mouth ownership');
    sync.setPlaybackVolume(.25);assert.equal(sync.outputGain.gain.value,.25,'Reader volume changes audible gain');
    sync.setPlaybackVolume(9);assert.equal(sync.outputGain.gain.value,2,'Volume is bounded');
    sync.setPlaybackVolume(0);assert.equal(sync.outputGain.gain.value,0,'Reader can mute');
    frame(1 / 60);
    assert.ok(viewer.weights.A > 0, 'Quiet speech animates the mouth');
    assert.equal(viewer.weights.I, 0, 'Speech uses one mouth shape without stretching the lips');
    amplitude = 1;
    for (let n = 0; n < 20; n++) frame(1 / 60);
    assert.ok(Object.values(viewer.weights).reduce((a, b) => a + b, 0) <= 0.45 + 1e-9);
    assert.equal(Object.values(viewer.weights).filter(value => value > 0).length, 1);
    amplitude = 0;
    for (let n = 0; n < 30; n++) frame(1 / 60);
    assert.ok(viewer.weights.A < 0.001, 'Mouth closes during silence');
    sync.stop(); await playing;
    assert.equal(frames.size, 0);
    const oldDecode = deferred(); decodeImpl = () => oldDecode.promise;
    const old = sync.playWithLipSync('old'); await tick();
    decodeImpl = async () => ({});
    const replacement = sync.playWithLipSync('new'); await tick();
    const latestSource = sync.source;
    oldDecode.resolve({}); await old;
    assert.equal(sync.source, latestSource, 'Late audio decode cannot replace new speech');
    latestSource.onended(); await replacement;
    assert.equal(sync.isPlaying, false);
    assert.equal(viewer.audioPlaybackActive, false, 'Audio mouth ownership ends with playback');
    assert.equal(sync.analyser, null);
    assert.equal(frames.size, 0);
    const pending = deferred(); fetchImpl = () => pending.promise;
    const cancelled = sync.playWithLipSync('pending'); await tick();
    sync.stop(); const count = sources.length;
    pending.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(1) }); await cancelled;
    assert.equal(sources.length, count, 'Stopping pending speech prevents later playback');
    fetchImpl = async () => ({ ok: false, status: 404 });
    await assert.rejects(sync.playWithLipSync('missing'), /Audio request failed/);
    console.log('PASS: frame-rate independence, quiet speech, bounded morphs, silence, cleanup, playback/decode races, HTTP errors');
})().catch(err => { console.error(err); process.exitCode = 1; });
