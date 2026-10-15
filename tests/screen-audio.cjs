const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
class Element {
    constructor() { this.checked = false; this.listeners = {}; this.children = []; }
    addEventListener(name, handler) {this.listeners[name] = handler;}
    append(...children) {this.children.push(...children);}
    replaceChildren() {this.children = [];}
    style = {};
}
const elements = Object.fromEntries(['group','enabled','sources','status','refresh'].map(id => ['screen-audio-'+id,new Element()]));
let active = false, speaking = false, onlyComputer = false, tick;
const calls = [], storage = new Map();
const context = {document:{getElementById:id=>elements[id],createElement:()=>new Element(),createTextNode:text=>text},
    localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)},
    setInterval:fn=>{tick=fn;return 1;},clearInterval(){},window:{addEventListener(){}}, fetch:undefined};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/screen-audio.js','utf8').replace('export function','function')+'\nthis.install=installScreenAudio;',context);
const request = async (url, options) => {
    if (url.endsWith('/sources')) return {ok:true,json:async()=>({sources:[{id:'default-output',kind:'output',name:'Speakers'},{id:'mic',kind:'input',name:'Microphone'}]})};
    const body = JSON.parse(options.body);calls.push(body);
    return {ok:true,json:async()=>({enabled:body.enabled,paused:body.paused,message:'Listening'})};
};
(async()=>{
    const control = context.install(()=>active,()=>speaking,request,()=>onlyComputer);
    await control.refresh(); await tick(); assert.equal(calls.length,0);
    active=true;await tick();assert.equal(calls.at(-1).enabled,true);assert.deepEqual(calls.at(-1).sources,['default-output']);
    speaking=true;await tick();assert.equal(calls.at(-1).paused,true);
    const mic=elements['screen-audio-sources'].children[1].children[0];mic.checked=true;mic.listeners.change();
    await new Promise(resolve=>setImmediate(resolve)); assert.deepEqual(calls.at(-1).sources,['default-output','mic']);
    onlyComputer=true;await tick();assert.deepEqual(calls.at(-1).sources,['default-output']);assert.equal(calls.at(-1).computer_only,true);
    onlyComputer=false;await tick();assert.deepEqual(calls.at(-1).sources,['default-output','mic']);
    active=false;await tick();assert.equal(calls.at(-1).enabled,false);
    control.setVisible(false);assert.equal(elements['screen-audio-group'].hidden,true);
    console.log('PASS: screen audio activation, source selection, playback pause, stop and tracking-only visibility');
})().catch(error=>{console.error(error);process.exitCode=1;});
