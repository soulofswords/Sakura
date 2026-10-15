const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let image = '/9j/test';
let allowed = false;
const context = {setInterval(){return 1;},clearInterval(){},window:{pywebview:{api:{
    set_screen_access: async value => {allowed=value;return value;},
    screen_snapshot: async () => image,
}}},document:{createElement:()=>({})}};
vm.runInNewContext(fs.readFileSync('static/js/screen-share.js','utf8').replace('export default class ScreenShare','globalThis.ScreenShare = class ScreenShare'), context);
(async () => {
    const share = new context.ScreenShare();
    await share.toggle();
    assert.equal(share.enabled,true);
    assert.equal(await share.snapshot(),image);
    share.stop();
    assert.equal(allowed,false);
    assert.equal(await share.snapshot(),null);
    image=null;
    await assert.rejects(share.toggle(),/no image/);
    assert.equal(share.enabled,false);
    assert.equal(allowed,false);
    console.log('PASS: desktop toggle verifies capture, awaits image, and rejects missing snapshots');
})();
