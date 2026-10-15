const assert = require('node:assert/strict');
const fs = require('node:fs'); const vm = require('node:vm');
let stream;
let capture = async () => stream;
let draws = 0;
const context = {setInterval(){return 1;},clearInterval(){},
    window: {},
    navigator: { mediaDevices: { getDisplayMedia(options) { assert.equal(options.audio, false); return capture(); } } },
    document: { createElement(type) {
        if (type === 'canvas') return { width: 1, height: 1,
            getContext() { return { drawImage() { draws++; }, clearRect() {} }; },
            toDataURL() { return 'data:image/jpeg;base64,/9j/'; } };
        return { videoWidth: 1920, videoHeight: 1080, readyState: 2,
            async play() {}, pause() { this.paused = true; } };
    } },
};
vm.runInNewContext(fs.readFileSync('static/js/screen-share.js','utf8')
    .replace('export default class ScreenShare', 'class ScreenShare') + '\nthis.ScreenShare = ScreenShare;', context);
function makeStream() {
    const track = { readyState: 'live', stopped: false, stop() { this.stopped = true; this.readyState = 'ended'; },
        addEventListener(name, fn) { this[name] = fn; } };
    return { track, getTracks() { return [track]; }, getVideoTracks() { return [track]; } };
}
(async () => {
    const share = new context.ScreenShare();
    assert.equal(share.enabled, false); assert.equal(await share.snapshot(), null); assert.equal(draws, 0);
    stream = makeStream(); await share.toggle();
    assert.equal(share.enabled, true); assert.equal(draws, 0, 'No automatic screenshot uploads');
    assert.equal(await share.snapshot(), '/9j/'); assert.equal(draws, 1);
    assert.equal(share.canvas.width, 1600);
    const old = stream; const video = share.video;
    await share.toggle(); assert.ok(old.track.stopped); assert.ok(video.paused);
    assert.equal(video.srcObject, null); assert.equal(await share.snapshot(), null);
    stream = makeStream(); await share.toggle(); stream.track.readyState = 'ended'; stream.track.ended();
    assert.equal(share.enabled, false); assert.equal(share.video, null);
    let resolve; capture = () => new Promise(r => { resolve = r; });
    const starting = share.toggle(); share.stop(); stream = makeStream(); resolve(stream); await starting;
    assert.ok(stream.track.stopped); assert.equal(share.enabled, false);
    capture = async () => { const err = new Error('cancelled'); err.name = 'NotAllowedError'; throw err; };
    await share.toggle(); assert.equal(share.enabled, false);
    console.log('PASS: default off, explicit capture, bounded snapshot, track shutdown, browser stop, cancelled picker');
})().catch(err => { console.error(err); process.exitCode = 1; });
