const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let time = 0, amplitude = 0, timer, submitted = 0, release;
const recordings = [], track = { stopped: false, stop() { this.stopped = true; } };
class Recorder {
    mimeType = 'audio/webm'; state = 'inactive';
    constructor() { recordings.push(this); }
    start() { this.state = 'recording'; }
    stop() {
        this.state = 'inactive';
        this.ondataavailable({ data: new Blob(['recording']) });
        this.onstop();
    }
}
class Context {
    async resume() {} async close() {}
    createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
    createAnalyser() { return { fftSize: 1024, getFloatTimeDomainData(a) { a.fill(amplitude); } }; }
}
const context = { setTimeout,clearTimeout,Blob, MediaRecorder: Recorder, Float32Array, performance: { now: () => time },
    window: { AudioContext: Context }, navigator: { mediaDevices: {
        async getUserMedia() { return { getTracks: () => [track] }; } } },
    setInterval(fn) { timer = fn; return 1; }, clearInterval() { timer = null; } };
vm.runInNewContext(fs.readFileSync('static/js/continuous-mic.js', 'utf8').replace(
    'export default class ContinuousMic', 'class ContinuousMic') + '\nthis.ContinuousMic = ContinuousMic;', context);
const tick = async () => { time += 50; timer?.(); await new Promise(r => setImmediate(r)); };
(async () => {
    const mic = new context.ContinuousMic(async () => {
        submitted++;
        await new Promise(r => { release = r; });
    }, () => {});
    await mic.start();
    for (let i = 0; i < 20; i++) await tick();
    assert.equal(submitted, 0, 'Silence cannot submit a request');
    amplitude=.6; await tick(); amplitude=0; for(let i=0;i<100;i++)await tick();
    assert.equal(submitted,0,'Sudden click noise must not submit');
    amplitude = 0.006; // Quiet speech used to fall below the fixed .012 floor.
    for (let i = 0; i < 10; i++) await tick();
    assert.equal(submitted, 0, 'Do not interrupt active speech');
    amplitude = 0;
    for (let i = 0; i < 10; i++) await tick();
    assert.equal(submitted, 0, 'Short pauses between words do not submit');
    for (let i = 0; i < 4; i++) await tick();
    assert.equal(submitted,0,'Keep the complete 700ms speech pause');
    await tick();
    assert.equal(submitted, 1, 'A completed phrase submits once');
    assert.equal(recordings[0].state, 'inactive', 'No recording during assistant reply');
    release(); await new Promise(r => setImmediate(r));
    assert.equal(recordings.at(-1).state, 'recording', 'Listening resumes after speech ends');
    const beforePause=submitted;
    mic.pauseCapture();assert.equal(mic.enabled,true,'Pausing output capture preserves microphone opt-in');
    assert.equal(recordings.at(-1).state,'inactive','Speaker playback discards an in-progress chunk');
    await new Promise(r=>setImmediate(r));assert.equal(submitted,beforePause,'Own speaker audio never submits as a new utterance');
    mic.resumeCapture();await new Promise(r=>setTimeout(r,650));assert.equal(recordings.at(-1).state,'recording','Listening resumes after the speaker-tail guard');
    mic.stop(); await new Promise(r => setImmediate(r));
    assert.equal(track.stopped, true);
    assert.equal(submitted, 1, 'Pause discards unfinished recording');
    console.log('PASS: silence, phrase boundaries, pause timing, reply isolation, resume and mute');
})().catch(e => { console.error(e); process.exitCode = 1; });
